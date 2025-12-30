from playwright.async_api import async_playwright
from browser_use import Agent, ChatOpenAI

import json
import asyncio
import time
from typing import List, Dict
from dataclasses import dataclass
from data import userData
from datetime import datetime
import os

info = userData()

@dataclass
class Job:
    url: str
    job_id: int
    status: str = "queued"
    assigned_agent: int = None
    started_at: datetime = None
    completed_at: datetime = None

class AgentWorker:
    def __init__(self, agent_id: int, browser, job_queue: asyncio.Queue, results: List):
        self.agent_id = agent_id
        self.browser = browser
        self.job_queue = job_queue
        self.results = results
        self.is_busy = False
        self.current_job = None
        self.context = None
        self.agent = None
        
    async def initialize(self, llm):
        """Initialize agent with its own context"""
        self.context = await self.browser.new_context()
        self.agent = Agent(
            task="You are a job application assistant. Complete the job application for the candidate.",
            llm=llm,
            browser_context=self.context
        )
        
    async def process_jobs(self):
        """Continuously process jobs from the queue"""
        while True:
            try:
                # Wait for a job (with timeout to allow checking for cancellation)
                try:
                    job = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                self.is_busy = True
                self.current_job = job
                job.status = "processing"
                job.assigned_agent = self.agent_id
                job.started_at = datetime.now()
                
                print(f"[Agent {self.agent_id}] Processing job {job.job_id}: {job.url}")
                
                # Process the job
                success = await self.apply_to_job(job.url)
                
                if success:
                    # Use the agent to fill out the form
                    try:
                        self.agent.task = f"Fill the candidate information using the following data: {info}. Complete all required fields in the job application form."
                        results = await self.agent.run()
                        print(f"[Agent {self.agent_id}] Agent completed form filling")
                        job.status = "completed"
                    except Exception as e:
                        print(f"[Agent {self.agent_id}] Error filling form: {e}")
                        job.status = "failed"
                else:
                    job.status = "failed"
                
                job.completed_at = datetime.now()
                self.results.append(job)
                
                duration = (job.completed_at - job.started_at).total_seconds()
                print(f"[Agent {self.agent_id}] Completed job {job.job_id} - Status: {job.status} - Duration: {duration:.2f}s")
                
                self.is_busy = False
                self.current_job = None
                self.job_queue.task_done()
                
            except asyncio.CancelledError:
                print(f"[Agent {self.agent_id}] Worker cancelled")
                break
            except Exception as e:
                print(f"[Agent {self.agent_id}] Error processing job: {e}")
                if self.current_job:
                    self.current_job.status = "failed"
                    self.current_job.completed_at = datetime.now()
                    self.results.append(self.current_job)
                self.is_busy = False
                self.current_job = None
                self.job_queue.task_done()
    
    async def apply_to_job(self, url: str) -> bool:
        """Apply to a job at the given URL"""
        page = None
        try:
            page = await self.context.new_page()
            await page.goto(url)
            
            # Look for apply buttons
            apply_selectors = [
                "text=Apply",
                "text=Submit Application",
                "text=Apply now",
                "button:has-text('Apply')",
                "a:has-text('Apply')"
            ]
            
            for selector in apply_selectors:
                try:
                    apply_button = page.locator(selector).first
                    if await apply_button.is_visible():
                        print("button located")
                        await apply_button.click()
                        await page.wait_for_load_state("networkidle")
                        print(f"[Agent {self.agent_id}] Successfully clicked apply button")
                        
                        await asyncio.sleep(2)
                        
                        return True
                except Exception:
                    continue
            
            print(f"[Agent {self.agent_id}] No apply button found")
            return False
            
        except Exception as e:
            print(f"[Agent {self.agent_id}] Error applying to job: {e}")
            return False
        
    
    async def cleanup(self):
        """Clean up resources"""
        if self.context:
            try:
                await self.context.close()
            except:
                pass


class ProtoType1:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.job_queue = asyncio.Queue()
        self.results = []
        self.workers = []
        self.worker_tasks = []
        
    async def initialize(self, job_list: List[Dict]):
        """Initialize browser and agents"""
        # Start playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        
        # Initialize LLMs
        llms = [
            ChatOpenAI(
                model="qwen/qwen-2.5-vl-7b-instruct:free",
                temperature=0,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url='https://openrouter.ai/api/v1'
            ),
            ChatOpenAI(
                model="xiaomi/mimo-v2-flash:free",
                temperature=0,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url='https://openrouter.ai/api/v1'
            ),
            ChatOpenAI(
                model="meta-llama/llama-3.1-405b-instruct:free",
                temperature=0,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url='https://openrouter.ai/api/v1'
            )
        ]
        
        # Create agent workers
        for i in range(3):
            worker = AgentWorker(i + 1, self.browser, self.job_queue, self.results)
            await worker.initialize(llms[i])
            self.workers.append(worker)
        
        # Add jobs to queue
        for idx, job_data in enumerate(job_list, 1):
            url = job_data.get("url")
            if url:
                job = Job(url=url, job_id=idx)
                await self.job_queue.put(job)
                print(f"Added job {idx} to queue: {url}")
        
        print(f"\n{len(job_list)} jobs queued. Agents will process them as they become available.\n")
    
    async def run(self):
        """Start all worker tasks"""
        # Create worker tasks
        self.worker_tasks = [
            asyncio.create_task(worker.process_jobs())
            for worker in self.workers
        ]
        
        # Create monitor task
        monitor_task = asyncio.create_task(self.monitor_status())
        
        # Wait for all jobs to complete
        await self.job_queue.join()
        
        # Cancel all tasks
        monitor_task.cancel()
        for task in self.worker_tasks:
            task.cancel()
        
        # Wait for tasks to finish cancelling
        await asyncio.gather(*self.worker_tasks, monitor_task, return_exceptions=True)
        
        print("\n\nAll jobs completed!")
        self.print_summary()
    
    async def monitor_status(self):
        """Monitor and display status"""
        try:
            while True:
                status = self.get_status()
                status_line = f"\rQueue: {status['queue_size']} | Completed: {status['completed']} | "
                status_line += " | ".join([f"Agent {a['agent_id']}: {a['status']}" for a in status['agents']])
                print(status_line, end="", flush=True)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            print()  # New line after status
    
    def print_summary(self):
        """Print summary of results"""
        print("\n" + "="*60)
        print("PROCESSING SUMMARY")
        print("="*60)
        
        completed = [j for j in self.results if j.status == "completed"]
        failed = [j for j in self.results if j.status == "failed"]
        
        print(f"Total jobs: {len(self.results)}")
        print(f"Completed: {len(completed)}")
        print(f"Failed: {len(failed)}")
        print()
        
        for job in self.results:
            duration = (job.completed_at - job.started_at).total_seconds() if job.started_at and job.completed_at else 0
            print(f"Job {job.job_id} (Agent {job.assigned_agent}): {job.status} - {duration:.2f}s")
            print(f"  URL: {job.url}")
    
    def get_status(self):
        """Get current status of all agents"""
        status = {
            "queue_size": self.job_queue.qsize(),
            "completed": len(self.results),
            "agents": []
        }
        
        for worker in self.workers:
            agent_status = {
                "agent_id": worker.agent_id,
                "status": "busy" if worker.is_busy else "idle",
                "current_job": worker.current_job.url if worker.current_job else None
            }
            status["agents"].append(agent_status)
        
        return status
    
    async def cleanup(self):
        """Clean up resources"""
        # Clean up workers
        for worker in self.workers:
            await worker.cleanup()
        
        # Clean up browser
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()


# Example usage
async def main():
    # Sample job list
    jobs = [
        {"url": "https://recruiting.ultipro.ca/MNP5000MNPL/JobBoard/062c8fba-7371-4cd7-9e8a-94a0b8019ffc/OpportunityDetail?opportunityId=ccfd8af6-bd8b-473a-be5a-faf85ebe2b73&source=LinkedIn"},
        {"url": "https://recruiting.ultipro.ca/MNP5000MNPL/JobBoard/062c8fba-7371-4cd7-9e8a-94a0b8019ffc/OpportunityDetail?opportunityId=ccfd8af6-bd8b-473a-be5a-faf85ebe2b73&source=LinkedIn"},
        {"url": "https://recruiting.ultipro.ca/MNP5000MNPL/JobBoard/062c8fba-7371-4cd7-9e8a-94a0b8019ffc/OpportunityDetail?opportunityId=ccfd8af6-bd8b-473a-be5a-faf85ebe2b73&source=LinkedIn"},
    ]
    
    # Initialize and process
    prototype = ProtoType1()
    
    try:
        await prototype.initialize(jobs)
        await prototype.run()
    finally:
        await prototype.cleanup()


if __name__ == "__main__":
    asyncio.run(main())