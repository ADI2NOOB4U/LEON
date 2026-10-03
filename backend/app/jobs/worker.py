import threading
import time
from datetime import datetime, timezone

from backend.app.jobs.task_manager import (
    get_next_queued_task,
    get_task,
    log_event,
    set_stage,
    update_task,
)


class LeonWorker:

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="LEON-Worker",
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            task = get_next_queued_task()

            if not task:
                time.sleep(1)
                continue

            self._execute(task)

    def _cancelled(self, task_id: int) -> bool:
        task = get_task(task_id)
        return bool(task and task["cancel_requested"])

    def _execute(self, task: dict):
        task_id = task["id"]

        update_task(
            task_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            set_stage(
                task_id,
                "planning",
                10,
                "Task plan initialized.",
            )
            time.sleep(2)

            if self._cancelled(task_id):
                return self._cancel(task_id)

            set_stage(
                task_id,
                "executing",
                30,
                "Execution started.",
            )

            for progress in (40, 55, 70, 80):
                time.sleep(1)

                if self._cancelled(task_id):
                    return self._cancel(task_id)

                update_task(
                    task_id,
                    status="executing",
                    current_stage="executing",
                    progress=progress,
                )

            set_stage(
                task_id,
                "verifying",
                90,
                "Verifying task result.",
            )
            time.sleep(2)

            if self._cancelled(task_id):
                return self._cancel(task_id)

            update_task(
                task_id,
                status="completed",
                current_stage="completed",
                progress=100,
                result=f"Task '{task['title']}' completed successfully.",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            log_event(
                task_id,
                "completed",
                "Task completed successfully.",
            )

        except Exception as exc:
            current = get_task(task_id)

            if current and current["retry_count"] < current["max_retries"]:
                retry_count = current["retry_count"] + 1

                update_task(
                    task_id,
                    status="queued",
                    current_stage="queued",
                    progress=0,
                    retry_count=retry_count,
                    error=str(exc),
                )

                log_event(
                    task_id,
                    "retry",
                    f"Retrying task ({retry_count}/{current['max_retries']}).",
                )
            else:
                update_task(
                    task_id,
                    status="failed",
                    current_stage="failed",
                    error=str(exc),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

                log_event(
                    task_id,
                    "failed",
                    str(exc),
                )

    def _cancel(self, task_id: int):
        update_task(
            task_id,
            status="cancelled",
            current_stage="cancelled",
            progress=0,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        log_event(
            task_id,
            "cancelled",
            "Task cancelled before completion.",
        )


worker = LeonWorker()
