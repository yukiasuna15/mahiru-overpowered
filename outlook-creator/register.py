#!/usr/bin/env python3
"""Outlook creator - non-headless via Xvfb."""
import asyncio, random, json, os
from datetime import datetime
import sys
# sys.path.insert(0, "<PATH_TO_VENV_SITE_PACKAGES>")  # or use hermes venv python
from cloakbrowser import launch_async

FIRST = ["alex","jordan","casey","morgan","taylor","riley","avery","quinn","dakota","sage","blair","finley","harper","rowan","skyler","logan","phoenix","river","eden","remi"]
LAST = ["smith","chen","patel","kim","garcia","mueller","santos","nguyen","brown","jones","wilson","moore","clark","hall","young","king","wright","lopez","hill","scott"]
MONTHS = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}

async def main():
    first, last = random.choice(FIRST), random.choice(LAST)
    email = f"{first}{last}{random.randint(100,999)}@outlook.com"
    password = f"Pass{random.randint(1000,9999)}!@"
    year = str(random.randint(1985, 2000))
    mn, dn = random.randint(1,12), random.randint(1,28)
    print(f"[*] {email} / {password} | {first} {last} | {MONTHS[mn]} {dn}, {year}")

    # Non-headless = real browser window (runs under Xvfb :0)
    browser = await launch_async(headless=False)
    page = await browser.new_page()
    try:
        await page.goto("https://signup.live.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        try:
            l = page.locator("text=Get a new email address")
            if await l.count() > 0: await l.click(); await asyncio.sleep(2)
        except Exception: pass

        # Email
        await page.locator("#MemberName, input[type='email']").first.fill(email)
        await asyncio.sleep(1)
        await page.locator("#iSignupAction, button:has-text('Next')").first.click()
        await asyncio.sleep(3)

        # Password
        await page.locator("input[type='password']").first.wait_for(timeout=10000)
        await page.locator("input[type='password']").first.fill(password)
        await asyncio.sleep(1)
        await page.locator("#iSignupAction, button:has-text('Next')").first.click()
        await asyncio.sleep(3)

        for step in range(4, 15):
            print(f"[{step}] {page.url}")

            # Name
            if await page.locator("text=Add your name").count() > 0:
                print(f"  -> Name")
                try: await page.get_by_label("First name").fill(first)
                except: await page.locator("input").first.fill(first)
                try: await page.get_by_label("Last name").fill(last)
                except:
                    inp = page.locator("input[type='text']")
                    if await inp.count() > 1: await inp.nth(1).fill(last)
                await asyncio.sleep(1)
                await page.locator("#iSignupAction, button:has-text('Next')").first.click()
                await asyncio.sleep(5)
                continue

            # Birthday
            if await page.locator("#countryDropdownId").count() > 0:
                print(f"  -> Birthday")
                await page.locator("#countryDropdownId").click(); await asyncio.sleep(0.8)
                await page.locator("[role='option']:has-text('United States')").first.click(); await asyncio.sleep(0.5)
                await page.locator("#BirthMonthDropdown").click(); await asyncio.sleep(0.8)
                await page.locator(f"[role='option']:has-text('{MONTHS[mn]}')").first.click(); await asyncio.sleep(0.5)
                await page.locator("#BirthDayDropdown").click(); await asyncio.sleep(0.8)
                await page.locator(f"[role='option']:has-text('{dn}')").first.click(); await asyncio.sleep(0.5)
                await page.locator("input[name='BirthYear']").first.fill(year); await asyncio.sleep(0.5)
                await page.locator("#iSignupAction, button:has-text('Next')").first.click()
                await asyncio.sleep(5)
                continue

            text = await page.evaluate("() => document.body?.innerText?.substring(0, 500)")
            tl = text.lower()

            if "blocked" in tl: print(f"  -> BLOCKED"); await page.screenshot(path="/tmp/outlook_blocked.png"); break
            if await page.locator("input[type='tel']").count() > 0: print(f"  -> Phone"); await page.screenshot(path="/tmp/outlook_verify.png"); break
            if "prove" in tl and "human" in tl: print(f"  -> Captcha"); await page.screenshot(path="/tmp/outlook_captcha.png"); break
            if any(x in tl for x in ["welcome", "your account", "let's go"]): print(f"  -> SUCCESS"); await page.screenshot(path="/tmp/outlook_success.png"); break
            print(f"  -> Unknown: {text[:200]}"); await page.screenshot(path="/tmp/outlook_unknown.png"); break

        acct = {"email": email, "password": password, "name": f"{first} {last}", "created": datetime.now().isoformat(), "url": page.url}
        af = os.path.join(os.path.dirname(__file__), "accounts.json")
        if os.path.exists(af):
            with open(af) as f:
                accts = json.load(f)
        else:
            accts = []
        accts.append(acct)
        with open(af, "w") as f: json.dump(accts, f, indent=2)
        print(f"\n[+] {email} / {password}")
    except Exception as e:
        print(f"[!] {e}")
        await page.screenshot(path="/tmp/outlook_error.png")
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
