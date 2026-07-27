# Gmail DroidRun trace

**Date:** 2026-07-27  
**Mode:** Direct local-device control through Mobilerun (the current DroidRun CLI)  
**Scope:** Read-only inspection of the visible Gmail inbox. No messages were opened, sent, marked read, archived, deleted, or otherwise changed.

## Objective

Repeat the Gmail inbox check and record each DroidRun action, including what the phone exposed after the action.

## Action trace

| Step | DroidRun action | Result | State change |
| --- | --- | --- | --- |
| 1 | `device start com.google.android.gm` | DroidRun launched Gmail and reported activity `.ConversationListActivityGmail`. | Gmail became the foreground app. |
| 2 | `device ui` | DroidRun read the active accessibility tree for the Gmail inbox. It identified the Primary tab, inbox rows, sender/subject previews, and the Compose button. | None—this is an inspection only. |
| 3 | Extract the five newest visible message rows from the accessibility-tree output. | Five visible email rows were available for a summary. | None—no row was tapped or opened. |

## What the accessibility tree exposed

The currently active Gmail screen exposed a structured list of elements rather than the whole mailbox. In particular, it provided:

- the active package: `com.google.android.gm`;
- the current activity: `MailActivityGmail`;
- the selected inbox tab: **Primary**;
- the text previews of messages currently on-screen; and
- actionable controls such as search, navigation drawer, and Compose.

It did **not** provide email bodies outside the visible previews, nor did this trace inspect messages beyond the displayed rows.

## Five newest visible emails — redacted summaries

1. **HDFC Bank InstaAlerts** — UPI transaction notification for a debit; transaction details intentionally redacted.
2. **HDFC Bank** — security alert about protecting a card from fraud.
3. **HDFC Bank InstaAlerts** — another UPI debit notification; transaction details intentionally redacted.
4. **Amazon via LinkedIn** — Amazon news covering satellite internet and safe-water initiatives.
5. **From you** — message with an image attachment; no subject or preview content was exposed in the visible row.

## Privacy and safety notes

- The trace launched Gmail and read UI metadata only.
- It did not tap an email row, so it did not intentionally mark an unread message as read.
- Financial amounts, account fragments, transaction IDs, recipients, and attachment identifiers are omitted from this file.
- A full agent run is not necessary for this repeatable read-only workflow; direct launch plus UI inspection makes the executed actions transparent and prevents a background agent from continuing after the trace.
