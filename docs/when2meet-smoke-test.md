# When2meet smoke test

Run this against a disposable poll while logged in to its participant account.

1. Confirm `UserID` is non-zero, then run the fill4you bookmarklet.
2. Check that the confirmation count matches the expected availability changes.
3. Accept it and verify that only the intended slots change; include a busy interval
   that starts or ends between 15-minute slot boundaries.
4. Include slots on multiple days and verify no rectangular cross-day selection is made.
5. Refresh When2meet and verify its normal save behavior retained the change.
6. Run it while signed out and verify that it refuses to write anything.
7. Revoke the bookmarklet token in fill4you and verify the old bookmarklet is rejected.
