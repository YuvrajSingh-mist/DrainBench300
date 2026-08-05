# DrainBench — Public Sample (3-Day Preview)

### Not the eval set. A structural preview only. **50 tasks total.**

**Grading model**: no separate rubric/LLM-judge "open-ended" bucket — a task either has everything it needs (deterministic, ADB-verified end state) or is missing one load-bearing fact the agent must actively ask for (agent-user interaction, resolved by an LLM playing the user, holding only the omitted fact, answering just what's asked).

Easy: 1 app, Medium: 1-2 apps randomly; exactly 1/3 steps respectively, varied phrasing. Hard battery: 2-3 apps, genuine reasoning, written as natural first-person requests rather than terse instructions, **distributed across the days and mixed so ask-user and deterministic tasks aren't grouped or predictable by position.**


---

## 3-Day Sample Schedule (50 tasks)


### Day 1


**[Gmail]**
- Easy (1pt): Star the most recent email from [sender] in my gmail inbox
- Medium (3pt): In Gmail, search my inbox for any recent shared documents that I have received in the past 3 days, star them, and move them to a label called: "Recent Documents Received: Must Check".

**[Google Maps]**
- Easy (1pt): On Google Maps, check the estimated arrival time if leaving right now for [place] from my current place.

**[Chrome]**
- Easy (1pt): In Chrome, check whether the Sony WF-1000XM5 wireless earbuds are back in stock this week on Amazon
- Medium (3pt): In Chrome, open two tabs for two different airlines' baggage policies, compare them, and note the stricter one

**[Google Drive]**
- Easy (1pt): Go to Google Drive and check which folder was modified most recently
- Medium (3pt): Find all files shared by [contact] this month, check which of those is an excel/spreadsheet file that was edited most recently, and download them locally to Documents folder through my gdrive.

**[Google Photos]**
- Easy (1pt): Save the lastest 3 invoices screenshots in photos to a new album named "Invoices"
- Medium (3pt): Find the top 5 best-matched photos taken in 'food' category from the year 2021-23,  and download the ones with highest resolution locally with the appropriate filenames to a folder called "Food Photos≠Memories 2021-23" in Downloads

**[YouTube]**
- Easy (1pt): Open YouTube and check if the most recent video on the 'Matt Wolfe' channel is about the latest news in the world of AI and technology. 
- Medium (3pt) **[YouTube+Telegram]**: Find the most viewed finance-related video saved in the Watch Later section, note its details with a shareable link into a SMS message to Maa if it's over 40 minutes from youtube app.

**[Telegram]**
- Easy (1pt): On Telegram, mute notifications for the most recent group chat

Hard tasks — Day 1:

**1. [Chrome+Notes] — DETERMINISTIC**
- I'm trying to book a flight and don't want to overpay — search Chrome for two competing prices on the same route from Indigo and Air India, check the fees in each, work out which is actually cheaper. Save that airline's name, url of the selected cheaper package and final price in a note with title: "Flight Booking" in the Notes app. The trip is from here to Mumbai, departing on 2026-08-15 and returning on 2026-08-20. Add in the timings of the package you choose to that note too and pin it.

**3. [Calendar+Clock] — ASK USER**
- I keep forgetting my dentist appointment is coming up — get it onto the Calendar, check whether anything else is already booked that morning, if so move it by two hours if something clashes. Set an alarm for that morning with snooze every 10 minutes, and add a backup alarm an hour later just in case (deliberately no appointment date and time exists anywhere on the test device). 

**6. [Google Maps+Telegram] — DETERMINISTIC**

- I've got a headache coming on and need something from a pharmacy right now — check Maps for the nearest one that's actually open, compare it against the second-closest option, note which one's genuinely faster to reach, text [contact] the winning pharmacy's name and hours through Telegram, and check the return route to my current location from there while you're at it.

**9. [Contacts+Telegram+Google Maps] — ASK USER**
- I'm so late for dinner tonight — pull up Yuvraj Airtel's number in Contacts, text him the address through Messages, check Maps for the current drive time, send that ETA as a follow-up text. Also, check the group thread in case anyone already gave them a heads up (deliberately no dinner address exists on the test device and no prior group thread exists, so the agent must ask the user for both to complete the task)

### Day 2

**[Google Search]**
- Easy (1pt): Fetch the top 3 search results for "best coffee shops near me".
- Medium (3pt) **[Google Search+Telegram]**: Google the operating hours for two competing stores for hardware/electronics around my location, note which opens earlier, and message [contact] on Telegram the better option with a shareable link to its website and its phone number.

**[Calculator]**
- Easy (1pt): Compute the total cost of 3 items priced individually at $15.99, $23.50, and $9.75, with calculator
- Medium (3pt) **[Calculator+Obsidian]**: Using the Calculator, open the Excel sheet/spreadsheet named 'PURCHASE_ORDER' from Downloads, add up the values in its 'Amount' column across all n rows to get the total purchase, work out how much a 5% sales tax adds to that total, compare it against a flat $10 fee, and save which option is cheaper in an Obsidian note titled "Sales Tax vs Flat Fee"

**[Clock]**
- Easy (1pt): Open Clock and check how many alarms are currently active
- Medium (3pt): Set an alarm for 7:30 AM tomorrow, check if it conflicts with any existing alarms, and if so, adjust it to 7:45 AM with snooze every 10 minutes for 3 times. Make sure it is at full volume and vibrate mode.

**[Calendar]**
- Easy (1pt): Check Calendar for whether any event, and if so, how many are scheduled during lunchtime today
- Medium (3pt): In the Google Calendar app, find all of my shareholder meetings this week (they have  the word "shareholder" prepended to the title), reschedule those after lunchtime to 9-12 in the morning, sorted by priority with a reminder of 15 minutes prior to each and get me a summary of meetings agendas from their descriptions.

**[Contacts]**
- Easy (1pt): In Contacts, change [contact]'s name to include their middle initial: [middle initial]
- Medium (3pt) **[Calendar+Contacts]**: From my contacts, find all people starting in the letter 'H' with birthdays this month, check which one will take place this week, and add a reminder in Calendar for it with the title: "Wish [contact] a happy birthday!"

**[Notes]**
- Easy (1pt): In Notes, rename the most recently edited note to an apprproiate name for its content, pinning it.
- Medium (3pt): On Notes, find all notes containing a checklist, order them by descending order of date and add the first checklists' unchecked items to my shopping cart on Amazon, and get it to the payments page.

**[Files]**
- Easy (1pt): Search Files for the spreadsheet named "SPORTS_VIDEO_DATA", open it in the google sheets app, find the video with the most views in it, and report back its name along with its view count and duration.
- Medium (3pt) **[Files+Google Drive]**: Sort the downloaded files by size and upload the 5 heaviest ones to google drive in a folder name "Too heavy files from Downloads" and remove it from the local storage thereafter to free up some space

Hard tasks — Day 2:

**2. [Messages+Contacts] — ASK USER**
- My cousin's wedding is next month and I've been put in charge of coordinating everyone — pull the family members who should be in the loop out of Contacts, start a new group chat in Messages called "Wedding Plans" so we can all coordinate, post the first planning meeting time in it, and pin the chat so it doesn't get buried (deliberately no family-member names are identifiable on the test device and no meeting time exists anywhere on it, so the agent must ask the user for both which contacts to include and the meeting time to complete the task)

**4. [Messages+Notes] — DETERMINISTIC**
- I htink my card payments are due — open Messages, find the 5 most recent bank or UPI transaction alert, note the exact amount and the date of the charge to a note called: "Card Payment Due" in the Notes app. Check today's date against it, set a reminder in Calendar with an appropriate title and in it, a line to double-check the charge if it's from today, and pin the same note so I remember to reconcile it

**7. [Files+Notes+Telegram] — DETERMINISTIC**
- The budget file's supposed to get updated every week and I'm worried it's slipping — check when 'budget.xlsx' in Downloads was last modified, note the date, and if it hasn't been touched this week, message [contact] through Telegram that it's overdue; save the last-modified date in a note titled "Budget Tracker" in the Notes app either way so we can track the pattern

**8. [Obsidian+Calendar+Clock] — ASK USER**

- It's Maa's birthday soon and I always forget until it's too late — check Maa's saved birthday in Contacts, get a Calendar reminder set a week ahead with title: "Maa's Birthday". Add an alarm that morning too, and check the calendar for any other birthdays coming up this month while you're in there, creating reminders before the actual dates, noting it in Obsidian with title: "Birthday Reminders" (deliberately no birthday date and time exists anywhere on the test device)

### Day 3


**[Camera]**
- Medium (3pt): Using Camera, record a 15-second video with front facing camera with highest resolution possible, saving it with the name: "Camera Video" to a "Pretty Memories" folder, while also sending it to [email-id] via gmail in the end

**[Gallery]**
- Easy (1pt): In Gallery, delete the most recent screenshot
- Medium (3pt): On Gallery, find all videos under 10 seconds, keep only the clearest one, and delete the rest

**[Music]**
- Easy (1pt): Play the latest song by [artist] on music app
- Medium (3pt): Create a playlist named "Chill Vibes" in my favourite app: YouTube Music , add the 5 popular lofi+jazz to it, and set it to shuffle play.

**[Messages]**
- Easy (1pt): Count number of unread messages in the past 2 weeks from banks.
- Medium (3pt): In Messages, look through the transaction alerts from the past month, sum up the total of all the purchase amounts mentioned in them (spending messages from stores and online services like PayPal, Kindle, OpenRouter and UPI payments), and send a summary to Dad via SMS with the total amount and a note: "Total spent on purchases this month is: ${total_amount}. Can I get you anything else?".


**[Phone]**
- Easy (1pt): Get me all the phone numbers ending with "89" from my recent call logs
- Medium (3pt): Save the first , unsaved number from my call logs today with the name: "Courier Service" to contacts and if there are any spam/fraud calls in the last 2 weeks, block them from calling me again

**[Settings]**
- Easy (1pt): Set the phone's screen timeout to if unused for over 1 minute
- Medium (3pt): Get the data on the app's usage for the past two weeks in terms of time spent on each app sorted in descending order, and set an app time limit to alert of about 30 minutes if any app is used for more than 2 hours in a day continuosly for past two weeks 

**[Shopping & Delivery (browser)]**
- Easy (1pt): Check the estimated restock date for the "ANC enabled wireless earbuds by Samsung" on Amazon
- Medium (3pt): Search for "Nike Air Jordans 1 Low" and compare prices for the same product with UK shoe size 10 on Amazon and Nike's official store site, note which one is cheaper than $1000 and add it to my cart on the cheaper site while also sharing the image's link


Hard tasks — Day 3:

**5. [Photos+Telegram] — ASK USER**
- Everyone's been asking about the trip — pull the vacation photos together in Photos, pick out the best recent ones in terms of resolution, create a new group called: "Trip 2026" and share them these photos on Telegram, pin the message so it doesn't get buried, and star a couple of your favorites for yourself too (deliberately no single obvious group or album exists on the test device)

**10. [Calendar+Gmail+Obsidian] — ASK USER**
- Sending an important client their quote is due today  — draft the number into mail in Gmail, send it over, andl also save a copy of the quote in Obsidian for my records, flagging it and set a reminder to follow up next week. The number is the sum of the 'Cost' column in the quote. (deliberately no client email id exists on the test device and the quote file's location isn't obvious, so the agent must ask the user for the client email and where the quote file is saved — then open it and total the Cost column itself for the amount)

**11. [Photos+Settings] — DETERMINISTIC**
- I want a proper lock screen made from my own photos for once — find 3 sharp photos in Photos, each of a different subject (a sunset, a beach, and a portrait), double-check each one is genuinely sharp at its best resolution, then make a single collage of all three and set that collage as the lock screen wallpaper through Settings, and star the three original photos in Photos so I remember which ones I used
