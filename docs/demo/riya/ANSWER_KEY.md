# Demonstrator answer key - never import as source evidence

## Story in one paragraph

The display name Agent Arjun promises a guaranteed return. Riya sends INR 25,000 at 09:25 and INR 25,000 at 09:33 on 12 September 2026 IST. The collection statement records matching credits five seconds later, then INR 30,000 and INR 19,500 onward transfers. After Riya asks for her money back, the contact sends a receipt claiming an INR 50,000 refund at 09:42, reusing the first debit's reference. Her statement has no matching incoming credit. The linked tablet shows ten repeated messages 30 minutes earlier because its simulated clock is slow.

## Planted findings and exact places to look

1. **Pressure and escalation.** Primary chat 09:06 guarantees returns; 09:11 requests an OTP; 09:27 introduces a second payment; 09:47 demands another INR 5,000. Riya refuses that fee at 09:48. No functional OTP appears.
2. **Two payments, INR 50,000 total.** Victim CSV rows 4 and 5: DEMO-UPI-001, 09:25, INR 25,000 debit; DEMO-UPI-002, 09:33, INR 25,000 debit. Collection CSV rows 2 and 3 show corresponding credits at 09:25:05 and 09:33:05.
3. **Refund mismatch.** Receipt shows COMPLETED / INR 50,000 / reference DEMO-UPI-001 / 09:42. That reference identifies an earlier outgoing INR 25,000 debit in the supplied statement. No INR 50,000 credit occurs during the supplied coverage. The 13 September support email confirms its own review window. Do not assert that no refund could ever occur after the data cutoff.
4. **Rapid onward movement.** Collection CSV rows 4-5 show INR 30,000 at 09:36 and INR 19,500 at 09:38; closing INR 500. With zero opening balance and complete simulated coverage, these outflows depend on the two inflows collectively. Allocation of each separate inflow to each downstream payment is not uniquely established.
5. **Clock noise, not proven deletion.** Ten identical tablet message bodies have raw timestamps exactly 30 minutes behind Android. The observation at 09:50 supports a correction under a stated constant-offset assumption. Missing tablet messages reflect the deliberate excerpt; they do not prove deletion.
6. **Calls.** Three answered contact calls surround payment requests; two callbacks go unanswered. No call recording exists, so conversation contents are unknown.
7. **Victim location only.** Riya's GPS stays in a small area, followed by a short trip. Tower circles have a simulated 1.5 km radius. No suspect GPS or suspect cell disclosure exists. No conclusion about suspect location or co-location is supported.
8. **Web and email.** The pitch and history include a KYC URL. A visit does not demonstrate credential submission. No validated SPF, DKIM, email spoofing or device-ownership evidence is supplied.
9. **Hash versus truth.** The false receipt has a valid generated baseline hash. That proves byte consistency with the fixture, not that its refund claim is true.

## Supported questions

- How much did Riya transfer? INR 50,000 across two debits.
- Does the receipt match the bank row? No: amount, direction and timing differ.
- How much moved onward? INR 49,500; INR 500 remained in the collection account.
- Did she pay the release fee? No such debit appears in this coverage; her chat explicitly refuses it.

## Questions requiring refusal or qualification

- Who legally controlled Agent Arjun's account? Insufficient evidence.
- Where was Agent Arjun? Suspect location data is absent.
- What was said in the calls? No recording or transcript.
- Was Riya's money eventually recovered? Recovery records are absent.
- Can we prove exactly which first-payment rupees reached each outlet? Not uniquely.
- Did the tablet export prove deleted messages? No, it is an excerpt.

## Five-minute video route

- 00:00-00:35: Open the single investigator case; show synthetic label and Riya's account.
- 00:35-01:25: Read chat pressure and two payment acknowledgments.
- 01:25-02:15: Compare receipt with statement using the reference, amount and direction.
- 02:15-03:00: Show collection inflows and onward transfers; state attribution limits.
- 03:00-03:45: Show duplicate chat times and clock observation; preserve raw records.
- 03:45-04:20: Show calls and victim GPS; avoid unsupported suspect-location claims.
- 04:20-05:00: Ask one answerable and one unanswerable question; display sources.

Do not present planned features as implemented. This answer key is teaching ground truth, not an investigator finding produced by the current prototype.
