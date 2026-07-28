# DrainBench-730 (v3)

### Everyday Queries for MobileAgentCostBench — medium and hard tiers rewritten to explicit step counts

315 easy + 315 medium + 78 hard-deterministic + 22 open-ended = **730 total**, across 21 apps.

Step-count discipline applied in this revision: **easy** = 1 step (unchanged). **Medium** = 2-3 steps — a find/filter/summarize step plus one or two follow-on actions (often a count, a conditional, or a second app-internal action), matching the pattern from the user's own Gmail edits. **Hard** = 3-5 steps, still cross-app where that was the point, with any 1-2 step hard tasks bumped to a genuine 3rd step. **Open-ended** is intentionally left unconstrained on step count — its grading is rubric/LLM-judge based (see methodology below), not step-counted.


---

## Easy (315)


**Gmail**
1. Check how many unread emails are in the inbox
2. Reply 'Sounds good, see you then' to the latest email
3. Mark the most recent email as unread
4. Star the latest email from [sender]
5. Delete the most recent promotional email
6. Archive the most recent email
7. Check if [sender] replied yet
8. Snooze the latest email until tomorrow morning
9. Open the most recent email with an attachment
10. Mute a noisy email thread
11. Check the sender of the most recent unread email
12. Forward the most recent email to [contact]
13. Star an email you'll need later today
14. Check the subject line of the oldest unread email
15. Compose a quick email to [contact] with subject 'Quick update'

**Google Maps**
1. Get the fastest route home from the current location
2. Check how busy [a saved place] usually is right now
3. Search for the nearest [type of place]
4. Check current traffic conditions on the usual commute route
5. Look up the opening hours for [place]
6. Check how far away [place] is
7. Find the nearest ATM
8. Get walking directions to [place]
9. Save the current location as 'parked here'
10. Check if [a saved place] is currently open
11. Download the map of [area] for offline use
12. Check the weather along today's commute
13. Find the nearest hospital
14. Look up reviews for [place]
15. Check the distance between two saved places

**Chrome**
1. Search 'weather tomorrow' and open the first result
2. Open a new incognito tab
3. Bookmark the current page
4. Reopen the most recently closed tab
5. Check if a website is down
6. Search for a phone number for [business]
7. Look up a word's definition
8. Check today's news headline for [topic]
9. Clear browsing history from the last hour
10. Set Chrome as the default browser
11. Translate the current page to English
12. Enable reader/simplified view on an article
13. Check the score of last night's [sport] game
14. Save the current page for offline reading
15. Find and enable saved password autofill for a site

**Google Drive**
1. Open the most recently edited document
2. Check current Drive storage usage
3. Rename the most recent upload to [X]
4. Star the most recently opened file
5. Search for a file named [X]
6. Check if a specific file has been shared with anyone
7. Open a PDF stored in Drive
8. Move a file into an existing folder
9. Check the last-modified date of a file
10. Restore a file from Trash
11. Copy a file to make a duplicate
12. Delete a file from Drive
13. Download a file for offline access
14. Check who has access to a shared document
15. Preview a file without opening it fully

**Google Photos**
1. Find photos from last weekend
2. Mark the most recent photo as a favorite
3. Search for photos of [subject]
4. Check how much storage the Photos backup is using
5. Delete the most recent screenshot
6. Check how many photos are in the library
7. Find the oldest photo in the library
8. Check which photos aren't backed up yet
9. Find a screenshot from earlier today
10. Look at 'On this day' memories
11. Search for videos from last month
12. Rotate a sideways photo
13. Crop the most recent photo
14. Search for photos from [date range]
15. Find a photo by approximate date

**YouTube**
1. Search for '[song name]' and play the first result
2. Subscribe to the channel of the video currently playing
3. Like the video currently playing
4. Check the watch history for today
5. Check trending videos today
6. Turn on captions for the current video
7. Mute the current video
8. Skip the ad on the current video
9. Check comments on the current video
10. Check if a specific channel has posted today
11. Adjust playback speed to 1.5x for the current video
12. Add the currently playing video to a new playlist
13. Resume a recently watched video from where it left off
14. Search for a music video by [artist]
15. Check how long a video is before playing it

**Telegram**
1. Send 'On my way' to [contact]
2. Mute notifications for [a specific group]
3. Check unread messages in the most recent chat
4. Pin the most recent message in [a group]
5. Search for [contact] and open their chat
6. Send a voice message to [contact]
7. Check the last-seen time for [contact]
8. Send a sticker to [contact]
9. Check a group's member list
10. Send your current location to [contact]
11. Star an important message for later
12. Leave a group that's no longer relevant
13. Turn off read receipts for a specific chat
14. Send a photo with a caption to [contact]
15. Check unread messages across all chats

**Google Search**
1. Search 'how to [topic]' and read the top result
2. Search for the definition of [word]
3. Check today's top news headline for [topic]
4. Search for the nearest [type of place]
5. Look up the current exchange rate for [currency pair]
6. Search for the current time in [city]
7. Search for tomorrow's sunrise time
8. Look up a unit conversion
9. Check today's date
10. Search for the calories in [food item]
11. Look up a random fact about [topic]
12. Search for the meaning of an acronym
13. Check the current temperature outside
14. Search for a nearby holiday or public event
15. Search for a synonym for [word]

**Calculator**
1. Compute an 18% tip on [amount]
2. Add [numberA] and [numberB]
3. Compute 15% of [amount]
4. Divide [amount] between [number] people
5. Compute a percentage discount on [amount]
6. Compute a 20% discount on [amount]
7. Convert [amount] between two currencies
8. Compute the square root of a number
9. Compute a 10% service charge on a bill
10. Convert a temperature between Celsius and Fahrenheit
11. Compute the area of a room given length and width
12. Split a bill evenly between 4 people
13. Compute a percentage for a school grade
14. Compute the total of three separate expense values
15. Compute a running total from a list of numbers read aloud

**Clock**
1. Set a 10-minute timer
2. Set an alarm for [time]
3. Check the time in a different timezone
4. Start the stopwatch
5. Delete an existing alarm
6. Check what time it is in [city]
7. Set a timer for boiling eggs
8. Set an alarm for a nap
9. Check how much time is left on the current timer
10. Set a bedtime reminder
11. Check the date a week from today
12. Set a quick 5-minute timer
13. Rename an alarm
14. Turn off all alarms for a day off
15. Check sunrise/sunset time via the world clock

**Calendar**
1. Check the next event today
2. Create an event titled '[X]' for tomorrow at [time]
3. Check what's scheduled this weekend
4. Delete a specific calendar event
5. Check for any conflicts tomorrow afternoon
6. Add a birthday reminder for [contact]
7. Check the time of the next event after lunch
8. See a list of all-day events this week
9. Add a note to an existing event
10. Check today's schedule at a glance
11. Set a reminder for an anniversary
12. Check for any events tagged 'personal'
13. See how many events are scheduled tomorrow
14. Add a location to an existing event
15. Move a meeting two hours later and notify attendees

**Contacts**
1. Call [contact]
2. Search for a contact named [X]
3. Add a new contact named [X] with a phone number
4. Star [contact] as a favorite
5. Check the phone number saved for [contact]
6. Check how many contacts are saved in total
7. Add a nickname to an existing contact
8. Add a birthday to an existing contact
9. Search contacts by company name
10. Set a custom ringtone for a specific contact
11. Check a contact's saved address
12. Add a second phone number to an existing contact
13. Mark a contact as an emergency contact
14. Check recently added contacts
15. Edit a contact's saved email address

**Notes**
1. Create a note titled '[X]'
2. Find the note titled '[X]'
3. Delete a specific note
4. Add a line to an existing note
5. Search notes for the word '[X]'
6. Add today's date as a heading in a new note
7. Check the most recently edited note
8. Add a photo to an existing note
9. Duplicate an existing note
10. Increase a note's font size
11. Check how many notes are in a specific folder
12. Move a note into a folder
13. Add a bullet list to a note
14. Lock a note with a password
15. Rename an existing note

**Files**
1. Find the largest file in Downloads
2. Rename the most recent downloaded file
3. Check total storage used on the device
4. Delete a specific file in Downloads
5. Search for a file named '[X]'
6. Check the file type of a specific downloaded file
7. Sort Downloads by date instead of name
8. Preview an image file without opening a gallery app
9. Rename a folder
10. Move a file to the Trash
11. Check when a specific file was last opened
12. Search for all PDF files on the device
13. Empty the Trash/Recently Deleted folder
14. Check available storage on an SD card if present
15. Check which folder is using the most storage

**Camera**
1. Take a photo and save it
2. Switch the camera to the front-facing lens
3. Take a photo in portrait mode
4. Record a short video
5. Take a screenshot of the current camera preview
6. Take a selfie
7. Turn on flash for a photo in a dark room
8. Take a photo with a timer delay
9. Switch to a square aspect ratio for a photo
10. Turn on grid lines for composition
11. Take a burst of photos quickly
12. Check how much storage is left for photos/videos
13. Take a photo with HDR mode on
14. Record a quick video with sound
15. Take a photo of a document and save it as a scanned file

**Gallery**
1. Find the most recent photo
2. Zoom in on the most recent photo
3. Delete the most recent photo
4. Rotate a sideways photo
5. Check how many photos were taken today
6. Check the file size of a specific photo
7. Search for videos only, not photos
8. Check the location metadata on a specific photo
9. Hide a specific photo from the main view
10. Star three photos in a row
11. Check the total number of videos in the gallery
12. Undo a recent edit made to a photo
13. Crop the most recent photo
14. Search the gallery for photos from [place]
15. Set a specific photo as a contact's photo

**Music**

**Music** — app-agnostic by design: tasks never name a specific app. The harness should detect whichever music app is actually installed/default on the test device (YT Music, Spotify, a local player, etc.) and drive that one, logging which app was used per run so results stay attributable. Whichever app ends up installed still carries its own automation terms at runtime (Spotify's is the strictest of the likely candidates) — the cleanest way to avoid that specific risk is simply not having Spotify installed on the benchmark device, rather than trying to steer around it in the task text.
1. Play a song by [artist]
2. Skip to the next track
3. Search for '[song]' and play it
4. Pause the currently playing track
5. Check what's currently playing
6. Search for a song by lyrics you remember
7. Like or save the currently playing song
8. Check the lyrics of the current song
9. Play a specific genre radio station
10. Check how long is left in the current song
11. Set a sleep timer to stop music after a set time
12. Search for a podcast by [name]
13. Play the most recently added song in a playlist
14. Shuffle the current playlist
15. Create a playlist named '[X]'

**Messages**
1. Send 'Running 10 minutes late' to [contact]
2. Check unread messages
3. Reply to the most recent message
4. Delete a specific conversation thread
5. Search messages for the word '[X]'
6. Check the read receipt on the last sent message
7. Send an emoji reaction to a specific message
8. Send a GIF in a conversation
9. Mark a conversation as unread for later
10. Copy text from a received message
11. Send your location in a message
12. Star an important message
13. Check the spam/blocked messages folder
14. Mute notifications for a specific thread
15. Reply to the most recent thread with a photo attached

**Phone**
1. Call [contact]
2. Check the most recent missed call
3. Return the last incoming call
4. Check today's call log
5. Block a specific incoming number
6. Check the contact name for an unknown incoming number
7. Turn on speakerphone during an active call
8. Check the total number of calls made today
9. Mute the microphone during an active call
10. Check voicemail greeting settings
11. Set a custom ringtone for unknown numbers
12. Check missed calls from today only
13. Redial the last dialed number
14. Merge two calls into a conference call
15. Set a reminder to call [contact] back later today

**Settings**
1. Turn on Do Not Disturb
2. Turn on Wi-Fi
3. Enable dark theme
4. Check current battery percentage
5. Turn on Bluetooth
6. Check available storage remaining
7. Turn on airplane mode
8. Check the device's current software version
9. Turn on location services
10. Turn on auto-rotate
11. Adjust screen brightness manually
12. Check which Wi-Fi network is currently connected
13. Turn on battery saver mode
14. Check available RAM/memory usage
15. Adjust screen timeout to a different duration

**Shopping & Delivery (browser)**
1. Search a shopping site via Chrome for '[product]' and open the top result
2. Check the delivery ETA for a recent order via the order-tracking page
3. Search for '[product]' on a shopping site and check its current price
4. Look up today's deals/offers page on a shopping site via Chrome
5. Check the return/refund policy for a recent purchase on a shopping site
6. Check a shopping site's flash-sale end time
7. Search for a specific brand's page on a shopping site
8. Check available sizes/colors for a specific product
9. Check the estimated delivery date before adding to cart
10. Search a shopping site's FAQ for a shipping question
11. Check if a store has a physical location nearby via its website
12. Search for a specific product's warranty information
13. Check whether a shopping site accepts a specific payment method
14. Search for gift card options on a shopping site
15. Check a food delivery site for any weather-related surcharge notice

---

## Medium (315) — 2-3 steps each


**Gmail**
1. Summarize the last 3 unread emails from [sender] in one line each
2. Find a noisy promotional thread and mute it
3. Filter the inbox to show only emails with attachments from this week, then star the 3 most recent ones
4. Find all emails from [sender] this month and archive them
5. Summarize today's promotional emails into a note on what to unsubscribe from
6. Filter and count how many emails came from [sender] in the past week and if it's more than 10, add the sender to spam
7. Find the 3 oldest unread emails, summarize them with the subject line, and then mark them read
8. Reply 'Got it, will follow up' to every unread email from today if the body is less than 20 words
9. Filter the inbox by attachment type (PDF only), list the senders, and count how many are from [sender]
10. Summarize the thread with [sender] into exactly 3 bullet points
11. Find and unsubscribe from the 3 most frequent promotional senders and add those emails to spam
12. Filter emails from the last 24 hours to only ones marked important, then forward the most recent one to [contact]
13. List today's emails ranked by how recently they arrived, and star the top 3
14. Find every email mentioning 'invoice' this month, total the amounts, and note the total
15. Filter unread emails to hide mailing lists, keep only 1:1 emails, and reply 'Thanks!' to the oldest one

**Google Maps**
1. Compare the ETA to [place] via driving vs. transit vs. walking, and pick the fastest
2. List the top 5 highest-rated restaurants within a mile, and save the top one to favorites
3. Filter search results for [type of place] to only ones open right now, then check the closest one's rating
4. Find the cheapest parking option near [place] and save it as a note
5. Rank three saved places by current travel time from home, and message the closest one's name to [contact]
6. Filter nearby coffee shops by rating above 4 stars, then pick the closest one
7. Summarize the reviews for [place] into pros and cons, and note the overall rating
8. Find a route to [place] avoiding tolls, compare the time added, and decide if it's worth it
9. List all saved places visited this month, and count how many were restaurants
10. Filter EV charging stations near the route by connector type, then check the nearest one's availability
11. Compare the ETA to [place] at two different times of day, and note which is faster
12. Find the nearest [type of place] with rating above 4.5 and wheelchair access, then save it as a favorite
13. Summarize traffic conditions across three routes to work, and pick the best one
14. Rank nearby gas stations by price, and save the cheapest one's location
15. Filter saved places to show only ones tagged 'restaurant', then count how many are currently open

**Chrome**
1. Find yesterday's page about [topic] in history, summarize what it said, and reopen it
2. Open three tabs comparing prices for [item], rank them cheapest to priciest, and note the cheapest
3. Research [topic] across two sources and summarize the key points into a note
4. Filter browsing history to show only visits from this week, then count how many are from one site
5. Compare two product pages, list the differences, and note which is the better deal
6. Summarize an article's main argument in 2-3 sentences, and save the summary as a note
7. Find the top 3 search results for [topic], note which seems most reliable, and open it
8. Filter open tabs down to just the ones about [topic], then close the rest
9. Search for step-by-step instructions for [task], summarize the steps, and save as a checklist note
10. Compare flight prices for [route] across two travel sites, and note the cheaper option
11. Search for reviews of [product], summarize the overall sentiment, and decide buy or skip
12. List the 5 most recently visited pages today, and bookmark the most useful one
13. Compare two recipes for [dish], note which needs fewer ingredients, and save that one
14. Summarize the return policy found on a store's page, and note the deadline
15. Filter bookmarks to show only ones added this month, then delete any duplicates

**Google Drive**
1. List the 5 most recently modified files, and open the most recent one
2. Filter Drive to show only files shared with you, and count how many you can edit
3. Summarize the contents of a specific document in 2-3 sentences, and save the summary as a note
4. Find all files over 50MB, list them by size, and delete the largest if unneeded
5. Filter files by type to show only spreadsheets, then open the most recent one
6. Compare two versions of the same document, note what changed, and keep the latest
7. Find and list files not opened in the last 6 months, then archive the oldest
8. Summarize comments left on a shared document, and reply to the most recent one
9. Filter shared files to show only ones you can edit, then star the most recent
10. Rank files in a folder by last-modified date, and open the oldest
11. Find every file shared by [contact], list them, and count how many are documents vs. sheets
12. Filter Drive search results to only PDFs from this year, then download the most recent
13. Summarize a spreadsheet's key totals into a note, and flag if any total exceeds a threshold
14. Find duplicate-named files across folders, and delete the older copy
15. List all folders sorted by total size, and note the largest

**Google Photos**
1. Find the 10 best photos from a specific trip based on favorites, and share them as an album
2. Filter photos to show only ones taken at [place], then count how many there are
3. Summarize how many photos were taken each month this year, and note the busiest month
4. Find and remove duplicate photos, and note how much storage was freed
5. Filter the library to show only videos over 1 minute long, then delete the longest if unneeded
6. Rank recent albums by number of photos, and open the largest one
7. Find photos not yet backed up, note how much storage they'd use, and start the backup
8. Filter for photos with faces not yet tagged, then tag the 3 most recent
9. Summarize a shared album's contents into a short caption, and post it
10. Find the 5 most recent photos of [subject], and add them to a new album
11. Filter screenshots older than a month, count them, and delete them in bulk
12. Compare storage used by photos vs. videos, and note which is larger
13. Group similar-looking photos, flag the extras, and delete them
14. Find photos taken with a specific mode (e.g. portrait), and count how many there are
15. List albums that haven't been viewed recently, and delete the least-used one

**YouTube**
1. List the top 5 recommended videos on the home feed, and save the most relevant one to Watch Later
2. Summarize what a video is about from its description and top comments, and decide whether to watch it
3. Filter the subscriptions feed to show only uploads from today, and count how many there are
4. Find and save the 3 most relevant tutorial videos for [topic] to a new playlist
5. Rank a channel's last 5 uploads by view count, and open the most-viewed
6. Filter watch history to show only videos over 20 minutes, then remove the oldest one
7. Summarize the top comment thread on a video, and like the top comment
8. Compare two videos on the same topic, note which is more thorough, and save that one
9. Find videos from a specific channel uploaded this week, and add the newest to Watch Later
10. Filter Watch Later to remove anything already watched, and count what's left
11. Summarize a podcast episode's key points from its description, and save the summary as a note
12. Rank saved playlists by number of videos, and open the largest
13. Find the most-liked video from a specific channel, and subscribe if not already
14. Filter the Shorts feed for a specific topic, then like the 3 best ones
15. Compare view counts across three videos on the same topic, and note which is most popular

**Telegram**
1. Summarize the last 10 messages in a busy group chat, and reply with a one-line update
2. Filter chats to show only ones with unread messages, and count how many need a reply
3. Find and list all messages from [contact] this week, and note how many were questions
4. Summarize a group discussion into 3 bullet points, and share the summary in the chat
5. Rank chats by number of unread messages, and open the top one
6. Search across all chats for a keyword, list which chats mention it, and reply to the most recent
7. Filter a group's shared media to show only photos from this month, then save the most recent
8. Find the 5 most active group chats this week, and mute the least relevant one
9. Summarize a long forwarded article shared in a chat, and reply with the summary
10. Filter contacts to find who hasn't messaged in over a month, and send one of them a check-in
11. Find all messages containing a link, list them, and open the most recent
12. Summarize what was discussed in a group while you were away, and note if action is needed
13. Rank groups by message volume today, and mute the noisiest one
14. Filter a chat for messages containing an address, and get directions to it
15. Find and summarize the most recent voice message from [contact], and reply based on it

**Google Search**
1. Compare the top 3 search results for [topic], summarize the differences, and pick the best one
2. Filter search results to only news from the last 24 hours, and note the top headline
3. Summarize the top result for '[topic] explained' in plain terms, and save it as a note
4. Rank three nearby [type of place] options by rating, and pick the highest-rated
5. Find and summarize the pros and cons of [a decision], and note a leaning
6. Compare prices for [product] across the top 3 results, and note the cheapest
7. Search for step-by-step instructions and summarize into a checklist, then save it as a note
8. Filter results to only ones from official/government sites, and open the most relevant
9. Summarize conflicting information found across two sources on [topic], and note which seems more credible
10. Find the 5 most relevant results for a specific how-to question, and open the top one
11. Compare visa requirements for two destinations, and note which is simpler
12. Rank local clinics by rating and distance, and save the top one as a contact
13. Summarize a product's warranty terms from its official page, and note the coverage period
14. Filter local event results to this weekend only, and pick one to add to the calendar
15. Compare public transit options for a specific route, and note the fastest

**Calculator**
1. Compute a monthly budget by summing 5 expense categories, compare to income, and note if it's over budget
2. Compute compound interest on a savings amount over 3 years, and note the final total
3. Compute how many months to pay off a debt at a fixed monthly payment, and note the payoff date
4. Rank three purchase options by total cost including tax, and note the cheapest
5. Convert a recipe's measurements from cups to grams across 6 ingredients, and log them in a note
6. Compute a weighted average of exam scores with different weights, and note the final grade
7. Compute the tip for a large group split unevenly by what each person ordered, and message each their share
8. Compute overtime pay given an hourly rate and extra hours across a week, and note the total pay
9. Compare the total cost of two financing plans for the same purchase, and note which is cheaper
10. Compute the total square footage of an apartment with multiple rooms, and note if it exceeds a target
11. Compute a currency-adjusted price comparison for the same product in two countries, and note the cheaper one
12. Compute a monthly savings plan to hit a goal amount in 6 months, and log the monthly figure in a note
13. Compute the break-even point for a small side project's costs vs. earnings, and note the month it breaks even
14. Compute fuel cost for a trip given distance, mileage, and gas price, and compare it to a stated budget
15. Compute each roommate's share of a shared bill with different usage levels, and message each their share

**Clock**
1. Set up a repeating interval timer for a workout routine, and confirm it starts on the first interval
2. Compare the current time across three saved world-clock cities, and note which is furthest ahead
3. Set a bedtime schedule, and check it doesn't conflict with an early alarm
4. Rank all set alarms by time of day, and delete the earliest if it's no longer needed
5. Set multiple back-to-back timers for a multi-step recipe, and label each one
6. Filter alarms to show only the ones that repeat weekly, then disable one
7. Set an alarm with a gradually increasing volume and a specific ringtone, and confirm it saved correctly
8. Convert a meeting time across two timezones, and set a matching local alarm
9. Set a Wind Down schedule based on a target wake-up time, and confirm the schedule saved
10. Compare snooze settings across two alarms, and make them consistent
11. Set three timers with different durations and labels for a cooking session, and confirm all three are running
12. Check which alarms would go off during a planned quiet-hours window, and disable those
13. Set an alarm that accounts for a timezone change on travel day, and confirm the local time is correct
14. Rank currently running timers by time remaining, and cancel the longest if not needed
15. Set a recurring alarm, and confirm it doesn't clash with an existing calendar event

**Calendar**
1. List the 5 busiest days on the calendar this month, and note the busiest one
2. Filter this week's events to show only ones with more than 2 attendees, and count them
3. Summarize tomorrow's schedule into a short morning briefing, and save it as a note
4. Find all events tagged 'work' this week, and total the hours booked
5. Rank next week's meetings by duration, and note the longest
6. Filter the calendar to find any double-booked time slots, and flag them in a note
7. Find a free 30-minute slot tomorrow, and book it as 'Focus time'
8. Summarize this week's schedule compared to last week's, and note which was busier
9. Filter recurring events to show only ones with no attendees, and delete one if outdated
10. Find and cancel just the next occurrence of a recurring event, and notify attendees
11. Compare two calendars for overlapping events, and flag the conflicts
12. List this month's events missing a location field, and add one to the nearest event
13. Rank today's events by how soon they start, and check the next one's location
14. Filter events this week that don't yet have a reminder set, and add reminders to them
15. Summarize which days this week are meeting-heavy vs. open, and block the open day for focus time

**Contacts**
1. Find all contacts missing a phone number, list them, and delete the ones with no other info
2. Filter contacts to show only ones added this month, and count how many
3. Merge duplicate contacts sharing the same phone number, and confirm only one remains
4. Rank contacts by how recently they were called, and star the most recent
5. Filter contacts by company name, and export the list
6. Find contacts with duplicate email addresses, and clean them up
7. Group several contacts into a new label like 'Family', and confirm the count
8. Filter contacts missing a photo, and add a photo to the most important one
9. Find contacts with an outdated area code, and update the most recent one
10. Summarize which contacts have birthdays this month, and add reminders for each
11. Compare two contacts that look like possible duplicates, and merge if confirmed
12. Filter starred contacts, and check they all have current numbers
13. Find contacts not called in the last 6 months, and count how many
14. Rank contact groups by number of members, and open the largest
15. Filter contacts by which ones have no email saved, and add one to the most important

**Notes**
1. Summarize the 5 most recently edited notes into one overview note
2. Filter notes to show only ones edited in the last week, and count them
3. Find and merge two related notes into one, and delete the originals
4. Summarize a long meeting note into 3 action items, and save them as a checklist
5. Filter notes by folder, and count how many are in each
6. Rank notes by length (word count), and open the longest
7. Find notes containing a specific date mentioned, list them, and open the most recent
8. Filter checklist notes to show only ones with unchecked items, and check off one item
9. Summarize a shopping-list note into categories, and reorganize the note accordingly
10. Find notes not opened in over a month, and delete the least useful one
11. Compare two versions of the same note idea, and consolidate them into one
12. Filter notes tagged or titled 'To Buy' across folders, and merge them into one list
13. Summarize a research note into a short takeaway, and save it at the top of the note
14. Rank folders by number of notes inside, and open the folder with the most
15. Find all notes mentioning a specific person's name, and count how many there are

**Files**
1. List the 5 largest files in Downloads, and delete the largest if unneeded
2. Filter Downloads to show only files from this week, and count them
3. Find and remove duplicate files in Downloads, and note how much storage was freed
4. Summarize how storage is split across folders, and note the largest category
5. Filter files by type to isolate all video files over 500MB, and delete the largest
6. Rank folders by total size, and open the largest
7. Find files not opened in over 3 months, list them, and delete the oldest
8. Filter Downloads to only .apk or installer files, and delete the ones no longer needed
9. Compare the sizes of two folders, and decide which to archive
10. Find all screenshots across folders, count them, and delete the oldest 10
11. Filter for files larger than 100MB across the whole device, and note the largest one
12. Summarize what's taking up the most space this month, and free up the biggest offender
13. Rank recently downloaded files by size, and delete the largest if unneeded
14. Find empty folders across storage, and delete them
15. Filter Downloads to isolate files that are already backed up, and delete them locally

**Camera**
1. Take 5 photos of the same subject, and identify the sharpest one
2. Compare a photo taken in normal mode vs. night mode for the same scene, and keep the better one
3. Take a burst of photos, keep only the best 2, and delete the rest
4. Take a photo, then trim/edit it before saving
5. Record a video, trim the start, and save the trimmed version
6. Take photos at 3 different zoom levels, and pick the best framing
7. Take a group photo using a timer, and confirm everyone's in frame
8. Take a photo in low light, compare flash vs. no-flash, and keep the better result
9. Take a panorama, and check it stitched without visible seams
10. Take a photo of a receipt, and confirm the text is readable
11. Record a slow-motion clip, and check playback quality
12. Take a photo with manual focus on a subject vs. auto-focus, and keep the sharper one
13. Take a series of product photos from different angles, and pick the best 3
14. Take a photo, apply a filter, and compare before/after
15. Take a video and a photo of the same moment, and decide which captures it better

**Gallery**
1. Find the 10 photos taking up the most storage, and delete the 3 least useful
2. Filter the gallery to show only photos from a specific trip, and count them
3. Batch-select and delete all screenshots older than a month, and note how many were removed
4. Rank recent albums by number of photos, and open the largest
5. Compare two similar photos, and delete the worse one
6. Filter for blurry or near-duplicate photos, and clean them up
7. Summarize how many photos were taken this month vs. last month, and note the difference
8. Create a GIF from a short burst of photos, and save it
9. Filter photos by which lens they were taken with, and count how many used portrait mode
10. Find and tag a group of untagged photos with a shared label, and confirm the tag applied
11. Merge two albums covering the same event into one, and delete the duplicate album
12. Rank videos by length, and flag the longest ones for review
13. Filter photos to find ones missing location metadata, and count them
14. Compare storage used by favorited vs. non-favorited photos, and note which is larger
15. Find photos taken at night, and check which ones came out usable

**Music**
1. Rank this week's most-played songs, and rebuild a playlist from the top 10
2. Filter liked songs to only ones from a specific genre, and count them
3. Summarize what a new album is about based on track titles, and decide whether to add it
4. Find and remove duplicate songs across two playlists, and confirm the count after
5. Compare two versions of the same song, note the difference, and keep the preferred one
6. Filter a large playlist to just songs under 3 minutes, and save it as a new quick-mix playlist
7. Rank followed artists by how often they're played, and unfollow the least-played
8. Find songs added to a playlist but never played, and remove them
9. Filter recently played to identify an 'on repeat' song this week, and add it to favorites
10. Merge two playlists into one, removing duplicates, and confirm the final count
11. Compare listening stats between this week and last week, and note the difference
12. Find the 5 longest tracks in a specific playlist, and move them to a separate playlist
13. Filter a workout playlist to keep only high-tempo songs, and remove the slow ones
14. Rank playlists by total listening time this month, and open the most-played
15. Find songs downloaded for offline listening that haven't been played in months, and remove them

**Messages**
1. Summarize an unread thread's messages into one line, and reply based on that summary
2. Filter conversations to show only ones with unread messages, and count them
3. Find and list all messages from [contact] this week, and note how many need replies
4. Rank threads by number of unread messages, and open the top one
5. Search across all conversations for a keyword, and list which threads mention it
6. Summarize a group thread's discussion while you were away, and reply if action is needed
7. Filter messages to find ones containing a shared link, and open the most recent
8. Find the oldest unread message, and reply to it now
9. Compare message volume from two contacts this week, and note who messaged more
10. Filter a thread for messages containing an address, and get directions to it
11. Rank contacts by how recently they messaged, and reply to the least recent
12. Summarize the tone of a conversation, and decide how to reply based on that
13. Filter threads to find ones with no reply in over 2 weeks, and reply to the oldest
14. Find all messages this week containing a question that wasn't answered, and answer one
15. Summarize today's messages into a short recap, and save it as a note

**Phone**
1. List the 5 most recent missed calls, and call back the most recent one not yet returned
2. Filter today's call log to show only calls over 5 minutes, and count them
3. Summarize this week's call history by contact, and note who called most
4. Rank contacts by number of calls this month, and note the top one
5. Find and merge a missed call's number into an existing contact, and confirm the merge
6. Filter call history to find calls from unknown numbers, and block the most frequent one
7. Compare call duration between two contacts this month, and note who you spoke to longer
8. Summarize a voicemail's key detail, and decide whether to call back based on it
9. Find calls from this week not yet logged with a note, and add a note to the most recent
10. Rank missed calls by how recently they came in, and return the most recent
11. Filter call log for international calls this month, and total the duration
12. Find repeat calls from the same unknown number, and block it as possible spam
13. Summarize today's voicemails into a short list of who to call back, and call the first one
14. Compare this week's call volume to last week's, and note the difference
15. Filter call history to find calls under 10 seconds, and note how many are likely missed connections

**Settings**
1. Check which apps used the most battery today, rank the top 3, and restrict the worst one
2. Filter installed apps to show which have camera permission, and revoke it for one unused app
3. Summarize today's screen time by app category, and note the largest category
4. Compare today's battery usage to yesterday's, and note the difference
5. Filter apps by storage usage, list the 5 largest, and clear cache for the top one
6. Rank notification-heavy apps by how often they alert today, and mute the noisiest
7. Filter location-permission apps to find ones that don't need it, and revoke access for one
8. Set up a scheduled dark mode from sunset to sunrise, and confirm the schedule saved
9. Compare Wi-Fi vs. mobile data usage this week, and note which is higher
10. Filter apps to find ones not opened in over a month, and uninstall one
11. Summarize which apps are set to run in the background, and disable one that's unnecessary
12. Rank apps by notification count this week, and turn off notifications for the noisiest
13. Filter storage usage to identify apps safe to offload, and offload one
14. Compare screen time this week to last week, and note the change
15. Find and list all apps with microphone permission, and revoke it for one unused app

**Shopping & Delivery (browser)**
1. Compare the price of '[product]' across three shopping sites, rank cheapest to priciest, and note the best deal
2. Filter search results for '[product]' to only ones with 4+ star ratings, and open the top one
3. Summarize the top 5 reviews for a product into pros and cons, and note whether to buy
4. Compare shipping costs and delivery windows across two options, and note the better one, without checking out
5. Rank three similar restaurants on a delivery site by rating and delivery time, and pick one
6. Filter a product category by price range, and list what qualifies
7. Compare a product's specs across two competing listings, and note which is the better value
8. Summarize a store's return policy vs. a competitor's, and note which is more lenient
9. Find the 3 highest-rated items in a product category, and note the top choice
10. Filter delivery options to show only ones arriving within 2 days, and pick the cheapest
11. Compare loyalty/rewards programs across two shopping sites, and note which offers more value
12. Summarize customer complaints mentioned in a product's reviews, and note the most common one
13. Rank menu items on a delivery site by rating for a specific restaurant, and pick the top one
14. Filter a wishlist/cart preview to only items currently on sale, and note the total savings
15. Compare total cost, item plus shipping, across two sites, and note the cheaper option

---

## Hard — Deterministic Composite (78) — 3-5 steps each, each pattern appears once

Graded the same way as easy/medium: independent ADB-based verifier, one correct end state, no LLM judge needed.

1. *[Gmail + Notes + Calendar]* Find the most recent bill from [company] in Gmail, note the amount, and set a calendar reminder to pay it
2. *[Gmail + Drive]* Find the most recent invoice email, download the attachment, and upload it to a Drive folder named 'Invoices'
3. *[Gmail + Calendar + Clock]* Find flight details in an email from [sender], add the flight to the calendar, and set an alarm 3 hours before
4. *[Maps + Telegram]* Get directions to [place] on Maps, check the ETA, and message [contact] on Telegram with the arrival time
5. *[Maps + Messages]* Check the live commute time to work on Maps; if over 40 minutes, message [contact] that you'll be late and suggest a new arrival time
6. *[Maps + Notes]* Search Maps for the nearest pharmacy, check its rating and hours, and save the details as a note
7. *[Telegram + Maps]* Find an address mentioned in an old Telegram chat with [contact], get directions to it on Maps, and share the ETA back in the chat
8. *[Chrome + Clock + Notes]* Check tomorrow's weather in Chrome; if it will rain, set an alarm 15 minutes earlier than usual and add 'bring umbrella' to a note
9. *[Chrome + Calendar]* Search Chrome for train times to [destination] tomorrow morning, add the earliest one as a calendar event, and set a reminder 30 minutes before
10. *[Chrome + Notes + Telegram]* Compare prices for [item] across two Chrome tabs, note the cheaper option, and share it with [contact] via Telegram
11. *[Photos + Drive + Telegram]* Upload the best five trip photos from Photos to a new Drive folder, share it with [contact], and message them that it's ready
12. *[Photos + Gmail]* Find a photo of [event] in Photos, email it as an attachment to [contact], and star the email once sent
13. *[Photos + Notes + Calendar]* Find the timestamp of the most recent photo in Photos, log it in a new note, and set a reminder to review the note tomorrow
14. *[Photos + Notes]* Find all photos from [place] in Photos, archive the rest of the album, and note how many were archived
15. *[YouTube + Notes + Calendar]* Find a recipe video for [dish] on YouTube, turn the ingredients into a checklist note, and add a reminder to buy them before this weekend
16. *[YouTube + Telegram]* Look up [topic] on YouTube, save the best result to Watch Later, and share the link with [contact] on Telegram
17. *[Telegram + Clock]* Find the last conversation with [contact] on Telegram, check the agreed meeting time, set an alarm 30 minutes before, and reply confirming the time
18. *[Telegram + Messages + Chrome]* Find the last message with a shared link (Telegram or Messages), reopen it in Chrome, and bookmark the page
19. *[Google Search + Telegram + Calendar]* Look up [business]'s hours via Google Search, message [contact] the hours via Telegram, and set a calendar reminder for the visit
20. *[Calculator + Notes + Calendar]* Sum three trip expenses on the Calculator, log the total in a note, and set a calendar reminder to review it
21. *[Calculator + Telegram + Clock]* Compute a bill split among a group on the Calculator, message each person their share via Telegram, and set a reminder to follow up in 3 days
22. *[Calculator + Notes]* Compute an order's total on the Calculator against a stated budget, note whether it's within limit, and if over, note which item to remove
23. *[Clock + Calendar]* Set a recurring alarm, cross-check it doesn't conflict with an existing calendar event, and adjust the alarm time if it does
24. *[Calendar + Notes]* Create a recurring monthly calendar event for a bill, link a note with the payment details, and set a reminder 3 days before each occurrence
25. *[Calendar + Telegram]* Reschedule the earliest calendar event tomorrow, message the attendee about the new time via Telegram, and update the event's reminder to match
26. *[Contacts]* Find all contacts with no phone number, list them, and delete them
27. *[Contacts + Drive + Telegram]* Export all contacts to a file, confirm it appears in Drive, and share the file with [contact]
28. *[Contacts + Gmail]* Find [contact]'s email in Contacts, send them a message via Gmail, and star the sent email
29. *[Contacts + Notes]* Find duplicate contacts sharing the same number, merge them, and log the merge in a note with the date
30. *[Notes]* Check the note titled 'To Buy' for [item], add it if missing, and reorder the list alphabetically
31. *[Chrome + Files]* Download a file via Chrome, rename it, and move it into a sorted folder in Files
32. *[Files]* Back up the Downloads folder to a folder named 'Backup', confirm it via Files, and delete the originals once confirmed
33. *[Camera]* Take a photo of a document with the Camera, save it as a scanned file, and rename it with today's date
34. *[Gallery + Notes + Telegram]* Curate today's Gallery photos into a dated album, log the count in a note, and share the album with [contact]
35. *[Gallery + Telegram]* Find a specific photo in Gallery, share it via Telegram, and star the photo
36. *[Music + Telegram]* Create a playlist, add two songs, and share the playlist name with [contact] via Telegram
37. *[Music + Telegram]* Check recently played, recreate a playlist matching this week's most-played tracks, and share the playlist name with [contact]
38. *[YouTube + Music]* Add a song mentioned in a YouTube video to a Music playlist, and like the song
39. *[Phone + Contacts + Notes]* Find the most recent missed call, save it as a contact named 'Unknown Caller', and log it in a note
40. *[Phone + Google Search + Telegram]* Check a missed call, look up the number via Google Search, and message [contact] about it
41. *[Phone + Clock + Notes]* Set a reminder-style alarm to call [contact] back based on the time of a missed call, and add a note of what to discuss
42. *[Settings + Calendar]* Schedule Do Not Disturb in Settings to match the start time of a calendar event, and confirm it ends when the event does
43. *[Settings + Notes]* Check today's screen time in Settings; if over your usual daily average, set an app timer for the most-used app and note the overage in a reminder
44. *[Gmail]* Find an email with a discount code, check if it's already expired based on the date mentioned, and archive it if so
45. *[Maps]* Save a frequently visited place (e.g. gym) as a Maps favorite, rename it with a short label, and check its current opening hours
46. *[Chrome + Notes]* Find a coupon code on a Chrome page, copy it, paste it into a note, and label the note with the store name
47. *[Drive + Notes + Telegram]* Check a shared spreadsheet's last-edited date in Drive, log in a note whether it's overdue against a given deadline, and if overdue, message [contact]
48. *[Photos + Telegram]* Create a shared Photos album for an ongoing event, enable auto-add for today's new photos, and invite [contact]
49. *[Photos]* Restore a recently deleted photo from the Photos trash, add it back to its original album, and star it
50. *[YouTube]* Turn on notifications for a specific YouTube channel, subscribe if not already, and confirm the bell icon shows 'all notifications'
51. *[YouTube]* Filter YouTube watch history older than a specific date, clear it, and confirm today's history is unaffected
52. *[Telegram + Notes]* Schedule a Telegram message to [contact] to send at a specific time later today, confirm the scheduled time shows correctly, and pin a reminder note about it
53. *[Telegram + Notes]* Change the notification sound for one specific Telegram chat, send a test message to confirm it plays, and note the sound chosen
54. *[Google Search + Calendar]* Look up a public transit line's next departure time via Search, add it as a calendar event, and set a reminder 10 minutes before departure
55. *[Google Search + Notes + Telegram]* Check a stock or currency value via Search against a threshold, log the result in a note, and if it crosses the threshold, message [contact]
56. *[Calculator + Notes + Calendar]* Convert a recipe's ingredients from 4 servings to 6 on the Calculator, log the new quantities in a note, and add a reminder to shop for them
57. *[Calculator + Notes]* Compute a monthly loan payment for a given principal and rate on the Calculator, log it in a note, and compare it to a stated budget
58. *[Clock]* Set three back-to-back alarms for a multi-leg travel day, confirm none conflict, and label each with its leg of the trip
59. *[Clock + Calendar]* Convert a meeting time across two timezones, set a local-time reminder, and note the timezone difference in the reminder
60. *[Calendar]* Find a free 30-minute slot tomorrow, book it as 'Focus time', and set a reminder 5 minutes before
61. *[Calendar]* Cancel just the next occurrence of a recurring event without deleting the series, note the reason in the event, and notify any attendees
62. *[Contacts + Maps + Notes]* Update a contact's saved address after confirming the new one on Maps, and save the old address in a note as backup
63. *[Camera + Contacts + Calendar]* Add a new contact from a business card photo taken with the Camera, and set a reminder to follow up with them this week
64. *[Notes + Calendar]* Pin an important note to the top of the notes list, add a due date as a heading, and set a reminder tied to the due date
65. *[Notes]* Convert a plain note into a checklist note, check off any items already done, and rename the note
66. *[Files]* Compress several files in Downloads into a single archive, rename it, and confirm the original files are still intact
67. *[Files]* Move all screenshots older than a week into an archive folder, count how many were moved, and delete any that are blurry
68. *[Camera + Telegram]* Take a panorama photo with the Camera, confirm it saved correctly, and share it via Telegram
69. *[Camera]* Record a short slow-motion clip with the Camera, trim it, and save the trimmed version
70. *[Gallery]* Tag a group of Gallery photos with a shared label, search by that label, and count how many match
71. *[Gallery + Settings]* Set a specific Gallery photo as the device wallpaper, confirm it applied to both lock and home screen, and star the photo used
72. *[Music]* Download a Music playlist for offline listening, confirm the download completed, and check how much storage it used
73. *[Music]* Set a 30-minute sleep timer on Music before it auto-stops, confirm the countdown started, and choose a calming genre to play
74. *[Messages + Notes]* Set a custom notification tone for one contact's Messages thread, send a test message to confirm it plays, and note the tone chosen
75. *[Phone + Settings + Telegram]* Add a new emergency contact in Phone settings, confirm it appears on the emergency dial screen, and share the contact's name with a family member via Telegram
76. *[Settings]* Save a second Wi-Fi network's password in Settings, confirm the device connects to it, and check the signal strength
77. *[Settings + Notes]* Turn on battery saver automatically when battery drops below 20%, confirm the setting saved, and note the current battery percentage
78. *[Settings + Notes]* Find yesterday's step count or activity data if available, log it in a note, and compare it to a stated daily goal

---

## Open-Ended (22) — step count intentionally unconstrained, see methodology below

1. *[Maps + Telegram]* Find a highly-rated coffee shop nearby that's open now on Maps, then send its location to [contact] on Telegram
2. *[Chrome + Google Search + Notes]* Research [topic] via Chrome or Search and summarize the findings in a new note titled [X]
3. *[Chrome + YouTube + Notes]* Find a how-to guide or tutorial for [task] and save the key steps as a note
4. *[Drive]* Find a document shared by [contact] in Drive and add comments with feedback
5. *[Photos + Telegram]* Find a photo matching a vague description (e.g. 'the one from the trip with the sunset') in Photos and share it via Telegram
6. *[YouTube]* Find a YouTube video matching a vague description and jump to the timestamp mentioned in the top comment
7. *[Google Search + Calendar]* Search [topic] via Google Search and create a calendar event based on a date mentioned in the results
8. *[Music]* Find a song matching a vague description ('that one from the ad') and add it to a Music playlist
9. *[Music + Telegram]* Build a Music playlist based on a mood description and share it with [contact]
10. *[Phone + Notes + Calendar]* Check the most recent voicemail, note the key detail, and add a calendar follow-up
11. *[Gmail + Messages]* Find the most important-looking unread message or email today and forward it to [contact]
12. *[Gmail]* Find the most urgent-seeming unread email today and reply to it appropriately
13. *[Maps]* Find a family-friendly restaurant nearby on Maps that roughly fits a stated budget
14. *[Chrome + Notes]* Research two competing viewpoints on [topic] via Chrome and note a balanced summary
15. *[Photos]* Pick the best photo from a burst of similar recent shots in Photos and delete the rest
16. *[YouTube]* Find a video that explains [topic] in simple terms on YouTube and save it
17. *[Google Search + Notes]* Find the most reputable-seeming source discussing [topic] via Search and note it
18. *[Music]* Curate a workout playlist in Music based on song energy, with no explicit song list given
19. *[Notes]* Rewrite a messy existing note into a cleaner, organized version
20. *[Gallery]* Choose the most flattering photo of a person from a Gallery album
21. *[Telegram]* Draft a polite decline message for an invitation, based on the context of an existing Telegram chat
22. *[Calendar]* Suggest and book the best meeting time tomorrow considering everyone's apparent calendar availability
---

## Grading the Open-Ended Bucket — Methodology

The 11 open-ended tasks above have no single correct final state — "find a highly-rated coffee shop" or "summarize findings" admit multiple valid answers. Grading them with the same pass/fail verifier used for deterministic tasks would either be too strict (penalizing valid alternatives) or meaningless (any completion "passes"). The research-backed approach instead:

**1. Decompose into binary, evidence-grounded rubric items — never a single 1–5 holistic score.**
Binary/atomic checks over concrete evidence (the final app state, a trace, an audit log) produce the same score on repeated evaluation of the same trace; holistic scores don't. For the coffee-shop task, that's checks like "a real, currently-open place was selected," "its rating is ≥4.0," "the message was actually sent to the named contact" — each a yes/no, each checkable against the device state or trace, not against the agent's own claim of what it did.

**2. Rubric criteria are task-specific, not fixed generic dimensions.**
A rubric built for "helpfulness/fluency" doesn't fit a goal-directed agent task. Each of the 11 tasks needs its own small checklist (3–5 items) written for what *that* task's success actually looks like — the summarization task's rubric ("note contains ≥2 concrete facts from source," "no fabricated claim contradicted by the source") looks nothing like the coffee-shop task's rubric, and reusing one template across both would silently reward or punish irrelevant properties.

**3. Never let a model judge its own family — self-preference bias is measured, not theoretical.**
Judges measurably favor their own family: one study found GPT-5 grading its own outputs roughly 4 points higher (on a 100-point scale) than an equivalent third-party judge would, and same-family effects for other model families ran even higher. Practical rule: the judge model must be from a different provider than every model under test in that run — never Claude-judges-Claude or GPT-judges-GPT.

**4. Calibrate the judge against a small human-labeled set before trusting it at scale.**
Production LLM-judge deployments calibrate against several hundred human-labeled cases before trusting aggregate scores — that's the right scale for continuous, high-volume production monitoring, not a hard minimum for an 11-task bucket. Right-sized for DrainBench: hand-label every open-ended task at least once per model under test, and check judge/human agreement on that set before reporting the judge's scores as reliable. If agreement is weak, fix the rubric before publishing numbers built on it — don't publish first and caveat later.

**5. Report this bucket's score separately from the deterministic hard-tier success rate — never blend them.**
A programmatically-verified pass/fail and an LLM-judge rubric score have different reliability profiles and different error bars. Folding them into one number hides which part of a model's score come from "actually got it right" versus "a judge model liked the answer." The leaderboard should show deterministic-tier success rate and open-ended rubric score as two separate columns.

**6. Track judge cost separately, too.**
Ensembling multiple judges (recommended to reduce single-judge bias) multiplies the judging token bill by however many judges are used — three judges is roughly three times the cost, before any human spot-checking. Since DrainBench's entire premise is honest cost accounting, the judging overhead itself needs to be logged and reported, not treated as a free add-on to the benchmark's own cost metric.