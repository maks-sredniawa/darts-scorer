---
layout: default
title: Privacy Policy
---

# Privacy Policy

_Last updated: 23 November 2026_

Darts Scorer is an Android app that scores a darts visit from a photo of the board. This policy
describes what the app does with the information you give it. It is short because the app does
very little.

## The app collects nothing

Darts Scorer has no account, no sign-in, and no server. **It never connects to a server**, and
nothing you give it is sent to the developer or to anyone else. The only connection it makes is
the one described under *The mounted camera* below: between your own two phones, on your own
network, and only if you set one up.

Everything it keeps is stored **only in the app's private storage on your own phone**, and is
readable only by the app.

There is no analytics, no crash reporting, no advertising, and no third-party SDK that phones home.
The Google Play Billing library, which handles tips, carries usage logging of its own, and it has no
way to send it: today the app has no permission to use the network at all, and the version that adds
the mounted camera leaves out the part of the library that would send the log.

## What the app can access, and why

- **The photos of the board you take or choose**, and, once you set one up, the photos your mounted
  camera takes. Finding the board and the darts in them runs on your phone, offline. The photos are
  never uploaded to a server or sent to anyone.
- **The camera, from the version that adds the mounted camera.** On a phone you set up as a mounted
  camera, to take the photo when you ask for it from your own phone. On your own phone, to open your
  camera app when you tap *Take a Photo*: once an app can use the camera at all, Android requires the
  permission for that too. The app asks the first time; if you say no, you can still choose a photo
  already on your phone. Today's version has no camera permission and asks for none: it hands the
  photo to your phone's own camera app, which needs no permission from this one.
- **The local network, from the version that adds the mounted camera.** Only to find your mounted
  camera on your Wi-Fi and receive its photo, never to reach the internet.
- **Google Play billing.** Lets the app ask the Google Play app for the price of a tip and open its
  payment sheet. It gives the app nothing about you.

## The mounted camera (coming in a later version)

A coming version of Darts Scorer lets you mount a spare Android phone beside the board and run the
app on it as a **mounted camera**. After a visit you tap on your own phone; the mounted camera takes
the photo and sends it to your phone, which scores it as it scores any other photo. The version you
have installed does not do this yet. When it does, this is what happens:

- **The photo goes only from the mounted camera to your own phone**, over your Wi-Fi, or over your
  phone's own hotspot. It is never sent to a server, to the developer, or to anyone else.
- **It travels encrypted, readable only by your two phones.** You pair them once: the mounted camera
  scans a QR code shown on your phone, or you paste its code into the mounted camera. From then on each phone talks only to the other, and a phone
  you have not paired can neither ask your mounted camera for a photo nor read one.
- **The mounted camera keeps nothing.** It sends the photo and forgets it, and stores no copy. On
  your phone the photo is kept exactly as one you took with your phone's own camera.
- **What pairing remembers stays on each phone**: each phone's own key, which only it can use, and
  which phone it is paired with. None of it is part of Android's backup. Unpairing on either phone
  ends the pairing.
- **If you never set up a mounted camera, none of this happens.** The one change you will notice is
  the camera permission the first time you tap *Take a Photo* (above).

## The things that happen outside the app

These are done by the operating system or by Google, not by Darts Scorer, but they are the honest
answer to "where could my data be":

1. **Android's automatic backup.** If it is enabled on your phone, Android backs up the app's
   settings, such as the theme and the language, to your own Google Drive, in a space that does not
   count against your storage quota and that Google states apps cannot read, and copies them to a new
   phone when you move to one. **Your photos are never part of it**, and neither is a mounted
   camera's pairing. You can turn this off in your phone's settings.
2. **Google Play.** Installing and updating an app is a transaction between your phone and Google,
   with its own privacy policy. About installs, the developer of this app receives aggregate,
   anonymous statistics — install counts, crash rates, country-level breakdowns — and no information
   about individuals.

   **A tip, if you leave one, is paid to Google Play.** The app asks the Play app on your phone for
   the prices and opens Play's own payment sheet; your payment details go to Google and never to the
   app. Tips unlock nothing, so the app keeps no record of one. The developer receives the payment
   and Google's order reports, which show for each tip the product, the price, your country, state
   and postcode, and the model of your phone — and your city, in the few countries where the developer
   rather than Google is the seller — but not your name or payment details. The developer uses them
   only for accounting.

## Children

The app is not directed at children and collects nothing from anyone.

## Deleting your data

Uninstalling the app removes everything it stored on the phone, a mounted camera's pairing
included. The only other copy is Android's backup of the app's settings in your Google account, if
backup is on; turn backup off in your phone's settings, or delete the backup under Backups in Google
Drive, to remove it.

## Changes

If this policy changes, the date at the top changes with it, and the history of this file is public
in the repository.

## Contact

**darts-scorer.support@maksforge.com**
