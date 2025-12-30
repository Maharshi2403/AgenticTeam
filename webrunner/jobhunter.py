from browser_use import Agent, ChatOpenAI, Browser

from dotenv import load_dotenv
from data import userData
import asyncio
import json
import os
# Read GOOGLE_API_KEY into env
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
userData = userData()
browser = Browser(
	headless=False,  # Show browser window
	 # Set window size
)

def candidate_info(url: str, user_info: json, login_email: str = None, login_password: str = None) -> str:
    task = f"""You are a job application assistant. Complete the entire job application process.

STARTING URL: {url}

USER INFORMATION:
{user_info}

INSTRUCTIONS:
1. First, navigate to the job application URL and wait for it to load completely
2. Look for "Apply", "Submit Application" or similar text and click it 
3. If you see a login/signup form:
   - Use login_email: {login_email or 'maharshi7178@gmail.com'}
   - Use login_password: {login_password or 'Maha1147@'}
   - Click login/submit button
4. Fill out ALL form fields using the user information above:
   - Personal details: name, email, phone, address
   - Work experience: previous jobs, responsibilities, dates
   - Education: degrees, schools, graduation dates
   - Skills and certifications
5. For file upload fields:
   - Look for resume upload and use the resume path from user data
   - Look for cover letter upload if available
6. Answer any additional questions based on user information
7. For dropdown menus, select the most appropriate option from user data
8. Check required checkboxes (terms, consent, etc.)
9. Click "Next", "Continue", or "Save and Continue" to move through pages
10. On the final review page, verify all information is correct
11. Click "Submit Application" to complete
12. Wait for confirmation message and verify submission was successful

IMPORTANT RULES:
- Take actions ONE AT A TIME and wait for page updates
- Read all visible text carefully before taking action
- If a field is required but not in user data, make a reasonable assumption
- Do NOT click Submit until ALL required fields are filled
- If you get stuck, try scrolling down to see more fields
- Always wait 2-3 seconds after clicking Next/Continue for page to load
"""
    return task

info = candidate_info(
    url="https://recruiting.ultipro.ca/MNP5000MNPL/JobBoard/062c8fba-7371-4cd7-9e8a-94a0b8019ffc/OpportunityDetail?opportunityId=ccfd8af6-bd8b-473a-be5a-faf85ebe2b73&source=LinkedIn",
    user_info=userData
)

# SOLUTION: Switch to Pro model which has higher rate limits
llm = ChatOpenAI(model='deepseek/deepseek-chat-v3-0324', api_key=DEEPSEEK_API_KEY, base_url='https://openrouter.ai/api/v1')




   
    
async def main(candidate_task_info: json):
    # Create agent with the model
    agent = Agent(
        task = candidate_task_info,
        browser=browser,
        llm=llm,
        use_vision=True  )

    history = await agent.run(max_steps=60)
    return history

if __name__ == "__main__":
    asyncio.run(main(info))