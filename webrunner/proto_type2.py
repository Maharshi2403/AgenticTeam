from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio


class ApplicationBot:
    def __init__(self, url):
        self.url = url
        self.state = 'inactive'  # Possible states: active, initiated, processing
        
    async def init(self):
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=False)
        self.state = 'active'
        
    async def process_application(self):
        self.page = await self.browser.new_page()
        await self.page.goto(self.url)
        # Add more steps to interact with the page as needed
        self.content = await self.page.content()

        with open('page.html', 'w', encoding='utf-8') as f:
            f.write(self.content)

        if self.state == 'active':
            print("Application process is active. Preparing to initiate form filling...")
            await self.application_init()
        
        if self.state == 'initiated':
            print("Application initiation successful. Proceeding to fill out the application form...")
            await self.application_process_form()
    
    async def application_init(self):
        button_text = ["APPLY NOW", "Apply now", "Apply"]

        for text in button_text:
            try:
                await self.page.get_by_role("button", name=text).click()
                print(f"Clicked on button with text: {text}")
                self.state = 'initiated'
                await asyncio.sleep(2)  # Wait for page to load after clicking
                break
            except Exception as e:
                print(f"Button with text '{text}' not found: {e}")

    async def application_process_form(self):
        # Get fresh content after button click
        self.content = await self.page.content()
        
        with open('page.html', 'w', encoding='utf-8') as f:
            f.write(self.content)
            
        soup = BeautifulSoup(self.content, 'lxml')
        
        # Find all potential user-input elements
        inputs = soup.find_all(['input', 'textarea', 'select'])
        
        # Filter for editable/user-providable ones
        user_inputs = []
        for elem in inputs:
            if elem.name == 'input':
                input_type = elem.get('type', '').lower()
                if input_type in ['hidden', 'button', 'submit', 'reset', 'reset', 'image', 'file']:
                    continue
            if elem.get('disabled') or elem.get('readonly') or elem.get('style', '').lower().find('display: none') != -1:
                continue
            
            details = {
                'tag': elem.name,
                'type': elem.get('type') if elem.name == 'input' else None,
                'name': elem.get('name'),
                'id': elem.get('id'),
                'placeholder': elem.get('placeholder'),
                'label': _get_associated_label(soup, elem)
            }
            user_inputs.append(details)
        
        print("Found user-providable input elements:")
        for idx, inp in enumerate(user_inputs, 1):
            print(f"{idx}. {inp}")
    
    async def cleanup(self):
        """Properly close browser and playwright"""
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'p'):
            await self.p.stop()


def _get_associated_label(soup, elem):
    """Helper to find <label> text for the input if available."""
    elem_id = elem.get('id')
    if elem_id:
        label = soup.find('label', {'for': elem_id})
        if label:
            return label.get_text(strip=True)
    return None


async def main():
    url = "https://edzt.fa.em4.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/32257?utm_source=linkedin&utm_medium=jobboard"
    
    bot = ApplicationBot(url)
    try:
        await bot.init()
        await bot.process_application()
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())