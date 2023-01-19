#/bin/env python3
# -*- encoding=utf8 -*-
#******************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# Author: miao_kaibo
# Create: 2020-10-22
# ******************************************************************************
"""
save package info
"""

import csv
import os
import sys
import time
import yaml
import threadpool

current_path = os.path.join(os.path.split(os.path.realpath(__file__))[0])
sys.path.append(os.path.join(current_path, ".."))
from common.log_obs import log
from common.parser_config import ParserConfigIni
from common.common import git_repo_src


class SaveInfo(object):
    """
    save info
    """
    def __init__(self, gitee_user, gitee_pwd):
        """
        init
        """
        parc = ParserConfigIni()
        self.file_name = parc.get_package_info_file()
        self.branch_prj = parc.get_branch_proj()
        self.need_ccb_branch = parc.get_need_ccb_branch()
        self.obs_pkg_rpms_url = parc.get_repos_dict()["obs_pkg_rpms"]
        self.release_management_url = parc.get_repos_dict()["release_management"]
        self.obs_pkg_rpms_files_dir = None
        self.release_management_files_dir = None
        self.gitee_user = gitee_user
        self.gitee_pwd = gitee_pwd

    def _download(self):
        """
        download obs_pkg_rpms
        """
        tmpdir = os.popen("mktemp").read().split("\n")[0]
        self.obs_pkg_rpms_files_dir = git_repo_src(self.obs_pkg_rpms_url, self.gitee_user, self.gitee_pwd, tmpdir)

    def _download_release_management(self):
        """
        download release-management
        """
        tmpdir = os.popen("mktemp").read().split("\n")[0]
        self.release_management_files_dir = git_repo_src(self.release_management_url, self.gitee_user, self.gitee_pwd, tmpdir)

    def _delete(self):
        """
        delete obs_pkg_rpms
        """
        cmd = "rm -rf %s" % self.obs_pkg_rpms_files_dir
        os.system(cmd)

    def save_unsync_package(self, package_name, branch_name):
        """
        save info
        package_name: package which is not be updated
        branch_name: branch of package
        """
        self._download()
        try:
            timestr = time.strftime("%Y%m%d %H-%M-%S", time.localtime())
            file_path = os.path.join(self.obs_pkg_rpms_files_dir, "unsync.csv")
            if branch_name in self.need_ccb_branch:
                branch_name = branch_name.replace("EBS-", "")
            log.info("package: %s, branch: %s" % (package_name, branch_name))
            with open(file_path, 'a') as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow([timestr, package_name, branch_name])
            cmd="cd %s && git add * && git commit -m 'update package info' && git push" % self.obs_pkg_rpms_files_dir
            for i in range(5):
                if os.system(cmd) == 0:
                    break
        except AttributeError as e:
            log.error(e)
        finally:
            self._delete()

    def _save_latest_info_by_pkg(self, datestr_root_path, prj, pkg, file_list, f_csv, code_update_time):
        """
        save latest info of package
        """
        if code_update_time == 0 or code_update_time:
            timestr = code_update_time
            cmd = "ccb ls -p %s %s 2>/dev/null | grep \"\.rpm\"" % (prj, pkg)
            log.debug(cmd)
            rpms = ' '.join(list(set(os.popen(cmd).read().replace(" ", "").replace('"', '').replace(",", "").split("\n")) - set([''])))
        else:
            if pkg in file_list:
                cmd = "cat %s/%s" % (datestr_root_path, pkg)
                log.debug(cmd)
                timestr = os.popen(cmd).read().replace("\n", "")
            else:
                timestr = 0
            cmd = "osc list -b %s %s 2>/dev/null | grep rpm" % (prj, pkg)
            log.debug(cmd)
            rpms = ' '.join(list(set(os.popen(cmd).read().replace(" ", "").split("\n")) - set([''])))
        f_csv.writerow([timestr, pkg, rpms])

    def save_latest_info(self, branch_name):
        """
        save latest info of package, include update time of package code and rpms
        """
        self._download()
        need_ccb = None
        code_update_time = 0
        try:
            prj_list = self.branch_prj[branch_name].split(" ")
            log.debug(prj_list)
            if branch_name in self.need_ccb_branch:
                branch_name = branch_name.replace("EBS-", "")
                need_ccb = "yes"
            datestr_root_path = os.path.join(self.obs_pkg_rpms_files_dir, branch_name)
            if not os.path.exists(datestr_root_path):
                os.makedirs(datestr_root_path)
            latest_rpm_file = os.path.join(self.obs_pkg_rpms_files_dir, "latest_rpm", "%s.csv" % branch_name)
            with open(latest_rpm_file, "w") as f:
                f_csv = csv.writer(f)
                file_list = os.listdir(datestr_root_path)
                var_list = []
                for prj in prj_list:
                    if need_ccb:
                        cmd = "ccb select builds build_type=full,incremental status=201,202 -f create_time os_project=%s build_target.architecture=x86_64 --sort create_time:desc --size 1 2>/dev/null | grep create_time | awk -F': ' '{print $NF}' | awk -F'.' '{print $1}'" % prj
                        log.debug(cmd)
                        res = os.popen(cmd).read()
                        if res:
                            code_update_time = res.replace('"', '').replace("T", " ").replace("-", "").replace(":", "-").replace("\n", "")
                        log.info("code_update_time:%s" % code_update_time)
                        cmd = "ccb select projects os_project=%s submit_order -f my_specs 2>/dev/null | grep spec_url" % prj
                        log.debug(cmd)
                        pkgs = []
                        res = os.popen(cmd).read().split("\n")
                        spec_url = [x for x in res if x != '']
                        if spec_url:
                            for url in spec_url:
                                p = url.split("/")[-1].split(".git")[0]
                                if p not in pkgs:
                                    pkgs.append(p)
                        else:
                            if not self.release_management_files_dir:
                                self._download_release_management()
                            if "epol" in prj.lower():
                                standard_dirs = ['epol']
                            else:
                                standard_dirs = ['everything-exclude-baseos', 'baseos']
                            release_management_path = os.path.join(self.release_management_files_dir, branch_name)
                            for c_dir in standard_dirs:
                                yaml_path = os.path.join(release_management_path, c_dir, 'pckg-mgmt.yaml')
                                if os.path.exists(yaml_path):
                                    with open(yaml_path, 'r', encoding='utf-8') as f:
                                        result = yaml.safe_load(f)
                                    for line in result['packages']:
                                        name = line.get("name")
                                        if name not in pkgs:
                                            pkgs.append(name)
                    else:
                        cmd = "osc list %s" % prj
                        log.debug(cmd)
                        pkgs = os.popen(cmd).read().split("\n")
                        code_update_time = None
                    for pkg in pkgs:
                        var_list.append(([datestr_root_path, prj, pkg, file_list, f_csv, code_update_time], None))
                try:
                    pool = threadpool.ThreadPool(20)
                    requests = threadpool.makeRequests(self._save_latest_info_by_pkg, var_list)
                    for req in requests:
                        pool.putRequest(req)
                    pool.wait()
                except KeyboardInterrupt as e:
                    log.error(e)
            cmd = "sort -u -r %s > tmp && cat tmp > %s" % (latest_rpm_file, latest_rpm_file)
            if os.system(cmd) != 0:
                log.error("sort file fail")
            cmd = "cd %s && git pull && git add * && git commit -m 'update file' && git push" % \
                    self.obs_pkg_rpms_files_dir
            log.debug(cmd)
            for i in range(5):
                if os.system(cmd) == 0:
                    break
        except AttributeError as e:
            log.error(e)
        finally:
            self._delete()


if __name__ == "__main__":
    s  = SaveInfo("xxx", "xxx")
    s.save_unsync_package("vim", "master")
    s.save_latest_info("openEuler-20.03-LTS-SP1")

