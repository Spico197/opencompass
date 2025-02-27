import os
import os.path as osp
import random
import subprocess
import time
from functools import partial
from typing import Any, Dict, List, Tuple

import mmengine
from mmengine.config import ConfigDict
from mmengine.utils import track_parallel_progress

from opencompass.registry import RUNNERS, TASKS
from opencompass.utils import get_logger

from .base import BaseRunner


@RUNNERS.register_module()
class DLCRunner(BaseRunner):
    """Distributed runner based on Alibaba Cloud Deep Learning Cluster (DLC).
    It will launch multiple tasks in parallel with 'dlc' command. Please
    install and configure DLC first before using this runner.

    Args:
        task (ConfigDict): Task type config.
        aliyun_cfg (ConfigDict): Alibaba Cloud config.
        max_num_workers (int): Max number of workers. Default: 32.
        retry (int): Number of retries when job failed. Default: 2.
        debug (bool): Whether to run in debug mode. Default: False.
        lark_bot_url (str): Lark bot url. Default: None.
    """

    def __init__(self,
                 task: ConfigDict,
                 aliyun_cfg: ConfigDict,
                 max_num_workers: int = 32,
                 retry: int = 2,
                 debug: bool = False,
                 lark_bot_url: str = None):
        super().__init__(task=task, debug=debug, lark_bot_url=lark_bot_url)
        self.aliyun_cfg = aliyun_cfg
        self.max_num_workers = max_num_workers
        self.retry = retry

    def launch(self, tasks: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
        """Launch multiple tasks.

        Args:
            tasks (list[dict]): A list of task configs, usually generated by
                Partitioner.

        Returns:
            list[tuple[str, int]]: A list of (task name, exit code).
        """

        if not self.debug:
            status = track_parallel_progress(self._launch,
                                             tasks,
                                             nproc=self.max_num_workers,
                                             keep_order=False)
        else:
            status = [self._launch(task, random_sleep=False) for task in tasks]
        return status

    def _launch(self, cfg: ConfigDict, random_sleep: bool = True):
        """Launch a single task.

        Args:
            cfg (ConfigDict): Task config.
            random_sleep (bool): Whether to sleep for a random time before
                running the command. This avoids cluster error when launching
                multiple tasks at the same time. Default: True.

        Returns:
            tuple[str, int]: Task name and exit code.
        """

        task = TASKS.build(dict(cfg=cfg, type=self.task_cfg['type']))
        num_gpus = task.num_gpus
        task_name = task.name

        # Dump task config to file
        mmengine.mkdir_or_exist('tmp/')
        param_file = f'tmp/{os.getpid()}_params.py'
        try:
            cfg.dump(param_file)

            # Build up DLC command
            pwd = os.getcwd()
            shell_cmd = (
                f'source {self.aliyun_cfg["bashrc_path"]}; '
                f'conda activate {self.aliyun_cfg["conda_env_name"]}; '
                f'cd {pwd}; '
                '{task_cmd}')

            tmpl = ('dlc create job'
                    f" --command '{shell_cmd}'"
                    f' --name {task_name[:512]}'
                    ' --kind BatchJob'
                    f" -c {self.aliyun_cfg['dlc_config_path']}"
                    f" --workspace_id {self.aliyun_cfg['workspace_id']}"
                    ' --worker_count 1'
                    f' --worker_cpu {max(num_gpus * 6, 8)}'
                    f' --worker_gpu {num_gpus}'
                    f' --worker_memory {max(num_gpus * 32, 48)}'
                    f" --worker_image {self.aliyun_cfg['worker_image']}"
                    ' --interactive')
            get_cmd = partial(task.get_command,
                              cfg_path=param_file,
                              template=tmpl)
            cmd = get_cmd()

            logger = get_logger()
            logger.debug(f'Running command: {cmd}')

            # Run command with retry
            if self.debug:
                stdout = None
            else:
                out_path = task.get_log_path(file_extension='out')
                mmengine.mkdir_or_exist(osp.split(out_path)[0])
                stdout = open(out_path, 'w', encoding='utf-8')

            if random_sleep:
                time.sleep(random.randint(0, 10))
            result = subprocess.run(cmd,
                                    shell=True,
                                    text=True,
                                    stdout=stdout,
                                    stderr=stdout)

            retry = self.retry
            output_paths = task.get_output_paths()
            while self._job_failed(result.returncode,
                                   output_paths) and retry > 0:
                retry -= 1
                if random_sleep:
                    time.sleep(random.randint(0, 10))
                # Re-generate command to refresh ports.
                cmd = get_cmd()
                result = subprocess.run(cmd,
                                        shell=True,
                                        text=True,
                                        stdout=stdout,
                                        stderr=stdout)
        finally:
            # Clean up
            os.remove(param_file)
        return task_name, result.returncode

    def _job_failed(self, return_code: int, output_paths: List[str]) -> bool:
        return return_code != 0 or not all(
            osp.exists(output_path) for output_path in output_paths)
