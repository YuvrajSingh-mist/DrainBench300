# Fabricated & Seeded Test Data — Disclosure

**Benchmark:** DrainBench300 (public sample: 50 tasks)
**Test device:** a stock, **non-rooted** Android phone
**Purpose of this document:** DrainBench evaluates an AI agent that operates a real
phone through UI automation. To make the *deterministic* (non-ASK-USER) tasks
actually solvable, a controlled, **fabricated test persona** was set up on the
device. This document discloses — fully and honestly — every piece of fabricated
data, how it was created, and where it lives, so that reviewers and downstream
users know exactly what was synthetic. **No real personal details are exposed**
(see [Privacy & Redaction](#privacy--redaction)).

---

## 1. Design principle: two task buckets

| Bucket | Meaning | Data policy |
|---|---|---|
| **Deterministic** | Task has a single correct, verifiable end state | All required data is **fabricated and seeded on-device** so the agent can find it |
| **ASK USER** | Task is deliberately missing one load-bearing fact | Data is **deliberately absent**; the agent must actively ask the simulated user for it. Nothing is fabricated for these |

The hard-task battery explicitly marks which tasks are ASK USER by noting in the
prompt that "no X exists anywhere on the test device" (see `public.md`). Those
facts are held only by the simulated user and answered only when asked
(`ask_user_facts.json`).

---

## 2. The test persona

All fabricated data belongs to a **fictional persona** ("Yuvraj Singh") and a set
of fictional family members, friends, and vendors:

- Family/people: `Maa`, `Dad`, `Dadima`, `Nanimaa`, `Mousi Maa`, and others
- Primary message recipient placeholder: `[contact]` = **Yuvraj** (a fictional
  contact, referred to in some task texts as "Yuvraj Airtel" / "Yuvraj Singh")
- A second fictional contact, **"Yuvraj Singh Jio"** (used in group-chat tasks)
- Service providers: `Harish Bakery`, `Himanshu CA`, `Harvinder`, and other
  H-prefix contacts used by the birthday tasks
- A fictional store/sender: `Myntra` (used for Gmail and transaction-alert tasks)

> All names above are **fictional test personas**, not real people. Phone numbers
> and personal email addresses are **redacted** in this document.

---

## 3. Fabricated data inventory (by app)

### 3.1 Contacts
- A contact database fixture (~hundreds of entries) reflecting the persona's
  family, friends, and vendors.
- Fictional contact **Yuvraj** (number redacted) — the default `[contact]`.
- Fictional contact **Yuvraj Singh Jio** (number redacted).
- **Birthday / anniversary records** on H-prefix contacts, used by the
  "birthdays this month" task:
  - Anniversary-type records (August): e.g. Harshit (Aug 5), Hariom (Aug 15),
    Hemant (Aug 20).
  - Genuine **birthday-type** records for H-contacts in August (Aug 4–7) are the
    intended target of that task and are added via the Contacts UI by the
    operator (see [Limitations](#6-known-limitations--honest-caveats)).

### 3.2 Calendar
- **Shareholder meetings** this week, prefixed with the word `shareholder`
  (required by the "reschedule my shareholder meetings" task):
  - `shareholder AlphaCorp Q2 Review`
  - `shareholder BetaTech Strategy`
  - `shareholder GammaFund Governance`
- Placeholder office/holiday events for general calendar tasks.
- Contact **anniversary dates** surface as calendar events.

### 3.3 Files (Downloads / Documents)
| File | Content / purpose |
|---|---|
| `PURCHASE_ORDER.xlsx` | Fabricated purchase order with an `Amount` column (Calculator total + tax task) |
| `SPORTS_VIDEO_DATA.xlsx` | Fabricated sports-video dataset (name, view count, duration) for the Files "most views" task |
| `budget.xlsx` | Last-modified **Jul 18, 2026** — deliberately "overdue" so the budget-tracker task has a clear answer |
| `quote.xlsx` | Fabricated quote with a `Cost` column totalling a **known figure** (₹4,500) for the "send the quote" task |
| `Project_Plan.docx`, `Team_Update.docx`, `Q3_Report.xlsx` | Prepared documents used for the Drive "files shared this month" task (see §3.6) |

### 3.4 Messages / SMS
- Fabricated **bank/UPI transaction alerts** (a bank the persona uses), dated
  early August, with fixed amounts — for the "recent card payments" task and the
  bank-unread-count task.
- Fabricated **store / online-service transaction alerts** (payments resembling
  PayPal, Kindle, OpenRouter, and UPI) — for the "sum up this month's purchases"
  task.

### 3.5 Gmail
- Emails from the fictional sender **Myntra** — for the "star the most recent
  email from [sender]" task.
- Emails matching "recent important alerts" — for the "Recent Alerts" label task.

### 3.6 Google Drive (server-side, operator action)
- **Files shared by the persona this month** cannot be fabricated on the device
  (sharing is a server-side Google operation). The operator uploads the prepared
  documents from §3.3 and shares them with the task's recipient address. This is
  the one piece of fabricated data that lives server-side, not on-device.

### 3.7 Photos
- **6 food images** (royalty-free stock photos, loremflickr `food` tag) for the
  "food photos in the last 2 weeks" task:
  - 3 at 1280×960 (higher resolution), 3 at 640×480 (lower resolution)
  - EXIF `DateTimeOriginal` + file mtime set to **Jul 20 – Aug 2, 2026**
    (spread across the 2-week window)
  - Pushed to `/sdcard/DCIM/Camera/`, indexed via the media scanner, and verified
    present in the Photos library with correct capture dates
- **3 invoice screenshots** (favorited) for the "Invoices album" task.
- **Pre-existing 2024-era photos** used by the lock-screen collage task (sunset /
  beach / portrait subjects already present on the device).
- Pre-existing WhatsApp images (late July) already on the device.

### 3.8 Call log
- **Nothing fabricated.** Call logs on a non-rooted device cannot be injected
  programmatically. The "unsaved number from call logs today" task requires the
  operator to make a real outgoing call to an unsaved number (see
  [Limitations](#6-known-limitations--honest-caveats)).

---

## 4. What was deliberately NOT seeded (ASK USER facts)

These facts exist **only** in `ask_user_facts.json` (held by the simulated user)
and are answered only if the agent asks:

| Task | Withheld fact |
|---|---|
| Wedding Plans group | Which family contacts to add; the planning-meeting time (Sat 6 PM) |
| Dentist appointment | Appointment date/time (Aug 5, 9:30 AM) and clinic |
| Trip 2026 group | The group name; which contacts to add; which photos |
| Maa's birthday | The birthday date (March 12) |
| Dinner address | The address (42 MG Road, Bhubaneswar); that no prior group thread exists |
| Client quote | The client's email address; that the quote is `quote.xlsx` in Downloads |

---

## 5. Run-time task variables

Tasks use placeholders that are filled at launch with persona values, e.g.
`sender=Myntra`, `contact=Yuvraj`, `place=<airport>`, `middle initial=<initials>`,
`email-id=<fabricated throwaway>`, `artist=<artist name>`. These are benchmark
parameters, not real-world data.

---

## 6. Known limitations & honest caveats

- **Photo categorization is on-device & asynchronous.** Google Photos tags
  images into the `food` category using on-device ML that runs in the background.
  The images are real food photos and the category pipeline is active, but
  tagging newly-added images can lag (minutes to hours). If the ML has not tagged
  them by run time, the agent may still find them via the recent-photos grid
  (dates are correct).
- **Call-log seeding is infeasible on a non-rooted device.** The "unsaved number
  today" task depends on an operator making a real call to an unsaved number on
  run day.
- **Drive shared files require a real secondary account.** On-device fabrication
  is impossible; sharing is done by the operator from a real Google account.
- **UI-based seeding is slow but reliable.** `content insert` is blocked on the
  non-rooted device, and VCF/ICS imports do not complete, so contact/calendar
  data is entered through the apps' own UIs.

---

## 7. Privacy & Redaction

- **No real phone numbers** appear anywhere in this document or the released
  benchmark data — all are redacted or fictional.
- **No personal email addresses** are exposed; the one client-style address used
  in the public task is a fabricated throwaway.
- All personas (family, friends, vendors, senders) are **fictional**.
- The benchmark is designed so that no real-world identity or account is
  reachable from the released tasks.

---

*This document is a truthful record of what was fabricated and why, so that any
reviewer can reproduce or audit the test environment.*
