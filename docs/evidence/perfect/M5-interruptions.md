# M5: surviving interruptions

## How it works now
- **Short drop.** When a computer's connection ends, `DirectorBroker.disconnect` keeps its tasks for 90 seconds (`GRACE_SECONDS`) instead of failing them. When the helper comes back on a new socket, `connect` sends every unfinished task again. The helper ignores a request it already has (running, waiting, or recently finished), so nothing runs twice. If the server cannot tell the old connection is dead yet, a *replacement* connection triggers the same re-send.
- **Long drop.** After the grace period the task fails with: "Claude on that computer lost its connection to this server and did not come back within 90 seconds. Open Video Tool there (its helper starts with the computer), or use a director on the server." The planning stage then keeps the rules' draft, records `who: rules` with that reason, and writes it to the video's notice. (Before, a failed client director was recorded as if it had directed the plan.)
- **Abandoned work is stopped.** A task the server gave up on (timeout, or grace over) is cancelled over there as soon as the computer returns, so an old planning session cannot later overwrite the fallback's plan.
- **Server restart.** Every `/ws` `hello` now carries `boot`, an id of this server process. A helper that sees a different id than last time stops the work that server was waiting for and drops answers it held for it. The same id after a reconnect leaves its work alone.
- **The helper resends** a finished answer it could not deliver (done in M2), for 10 minutes.
- **Remembered computers.** Computers that were connected are saved in the data folder (`directors-seen.json`, kept 60 days). The director list shows a missing one as "Claude on <name>", not available, "Not connected. Open Video Tool on that computer; its helper starts with it and reconnects by itself." A video whose picked director is missing says so: "Claude on Laptop was not available (Not connected. ...), so Local AI directed this video."

## Checks
- Python (`tests/test_one_director.py`, 7 new tests): a short drop, a replaced connection, a long drop with the cancel on return, a whole video whose director never returns (records `rules`, plain notice, no half-made plan credited to Claude), a picked director that is not connected, computers remembered across a new broker, and `boot` in the first message of a real `/ws`. The old test that expected an instant failure on disconnect now states the new rule (`DirectorBroker(grace=0)`).
- Eight deliberate breakages each fail a test: no re-send, no re-send for a replaced connection, grace ignored, no cancel on return, nothing remembered, failed director credited again, no notice for a missing picked director, no boot id.
- JS (`client/desktop/test-helper.js`, six runs in a row): a request sent twice is run once, even after it finished; a different boot id stops the old server's work and the same id does not.
- The wider run: 136 passed (director, provider, job, API and server-auth test files), and the desktop `npm test` passes.

## Not done here
- Falling through to the next director (for example the local AI) after a client director fails is step B10. Today the rules' draft stays, with the notice.
- A real network drop on a built app (unplugging the cable) is step M10.
