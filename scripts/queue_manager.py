import os
import time
import psutil
from pathlib import Path

class HDS_Queue_Manager:
    def __init__(self, queue_dir):
        self.queue_dir = Path(queue_dir)
        self.lock_file = self.queue_dir / "active.lock"
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def _clean_stale_tasks(self):
        """Видаляє застарілі локи та пендінг-файли, чиї процеси вже не існують."""
        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text().strip())
                if not psutil.pid_exists(pid):
                    self.lock_file.unlink(missing_ok=True)
            except:
                self.lock_file.unlink(missing_ok=True)

        for pfile in self.queue_dir.glob("*.pending"):
            try:
                parts = pfile.stem.split('_')
                if len(parts) >= 4:
                    pid = int(parts[-1])
                    if not psutil.pid_exists(pid):
                        pfile.unlink(missing_ok=True)
            except:
                pass

    def wait_for_turn(self, task_id, priority=10):
        task_file = self.queue_dir / f"{priority}_{task_id}_{os.getpid()}.pending"
        task_file.touch()
        
        while True:
            self._clean_stale_tasks()
            all_pending = sorted(list(self.queue_dir.glob("*.pending")))
            if all_pending and all_pending[0] == task_file:
                if not self.lock_file.exists():
                    self.lock_file.write_text(str(os.getpid()))
                    task_file.unlink(missing_ok=True)
                    return True
            time.sleep(1)

    def release(self):
        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text().strip())
                if pid == os.getpid():
                    self.lock_file.unlink(missing_ok=True)
            except:
                pass
