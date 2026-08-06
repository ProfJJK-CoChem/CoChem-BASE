# cochem_canvas_target: core_engine/cochem_core_scheduler.py
"""
Scheduler module for CoChem-CORE.
Manages scheduling and queuing of computational chemistry tasks.
"""

import time
import threading
from pathlib import Path
from typing import Dict, List, Optional

class CoreScheduler:
    """
    Schedules and manages computational tasks across the system.
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self.task_queue = []
        self.running_tasks = {}
        self.is_running = False
        
    def add_task(self, task_id: str, task_data: dict):
        """Add a task to the scheduling queue."""
        print(f"📥 Adding task {task_id} to queue")
        self.task_queue.append({
            'id': task_id,
            'data': task_data,
            'submitted_at': time.time()
        })
        
    def schedule_next_task(self):
        """Schedule the next available task."""
        if not self.task_queue:
            print("📭 No tasks in queue")
            return None
            
        task = self.task_queue.pop(0)
        print(f"🕒 Scheduling task {task['id']}")
        self.running_tasks[task['id']] = {
            'status': 'running',
            'started_at': time.time()
        }
        return task
        
    def complete_task(self, task_id: str):
        """Mark a task as completed."""
        if task_id in self.running_tasks:
            self.running_tasks[task_id]['status'] = 'completed'
            self.running_tasks[task_id]['completed_at'] = time.time()
            print(f"✅ Task {task_id} completed")
            
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get the status of a specific task."""
        return self.running_tasks.get(task_id)
        
    def start_scheduling(self):
        """Start the scheduler."""
        self.is_running = True
        print("🔄 Scheduler started")
        
    def stop_scheduling(self):
        """Stop the scheduler."""
        self.is_running = False
        print("🛑 Scheduler stopped")

def main():
    """Main entry point for the scheduler."""
    print("Starting CoChem-CORE Scheduler")
    
    scheduler = CoreScheduler()
    scheduler.start_scheduling()
    
    # Example usage
    scheduler.add_task("test_task_1", {"type": "dft_calculation"})
    scheduler.add_task("test_task_2", {"type": "optimization"})
    
    task = scheduler.schedule_next_task()
    if task:
        scheduler.complete_task(task['id'])
        
    scheduler.stop_scheduling()

if __name__ == "__main__":
    main()