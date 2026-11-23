### The verdicts, taken 2026-11-23

Both read with a throwaway app on emulator 37.2.13, headless, its code on the branch
[`spike/phase-g-link`](https://github.com/maks-sredniawa/darts-scorer/tree/spike/phase-g-link)
(`spike/`, one Activity driven by `adb shell am start` extras, logging under `LinkSpike`), which is
never merged. The excerpt below is the part C carries over.

**Keystore keys and mutual TLS: verdict 1, as designed, with one condition on the key.**

- `urgent-api26` and `pixel-api36`, each as both roles in turn, a Keystore EC P-256 key on each side,
  client authentication required, each side pinned to the other's SHA-256 fingerprint, the
  connection carried by `adb forward` because API 26 is not on the shared Wi-Fi (below): both
  directions handshake, `TLSv1.2 TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256`, and a line goes each way.
  Pinned to the wrong fingerprint, the camera side refuses the handshake
  (`SSLV3_ALERT_CERTIFICATE_UNKNOWN` on the other end).
- The same handshake inside one app, two Keystore keys, on API 26 (TLS 1.2), 30, 36 and 37 (TLS 1.3,
  `TLS_AES_128_GCM_SHA256`); and across emulators over the shared Wi-Fi between 33, 36 and 37 (TLS
  1.3), found by NSD.
- **The condition: the key must allow `KeyProperties.DIGEST_NONE` besides `DIGEST_SHA256`.** The
  platform's TLS hashes the handshake itself and asks the Keystore to sign the digest, so a key
  limited to `DIGEST_SHA256` fails every handshake, on API 26 and 36 alike: keystore2 logs
  `Digest 0 was specified, but not authorized by key` → `INCOMPATIBLE_DIGEST`, and the TLS layer
  sees only a closed connection. With `DIGEST_NONE` added, every reading above passes. The key is
  still sign-only and never leaves the Keystore; no software key, no Bouncy Castle.

```kotlin
KeyGenParameterSpec
    .Builder(alias, KeyProperties.PURPOSE_SIGN)
    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
    .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
    .build()
// TLS: an X509KeyManager returning that PrivateKeyEntry's key and its one self-signed certificate,
// an X509TrustManager that throws unless chain[0]'s SHA-256 is the pinned one, and
// SSLServerSocket.needClientAuth = true on the Mounted camera.
```

**NSD between emulators: verdict 2, only the newer images join the shared Wi-Fi.**

| Image | Wi-Fi address | Shared Wi-Fi | NSD both ways with `pixel-api36` | Lock taken by the rule |
| --- | --- | --- | --- | --- |
| `urgent-api26` | 192.168.232.2 | no, its own router | no, either way | yes |
| `small-api30` | 10.0.2.16, the same as `pixel-api36`'s | no | no, either way | yes (extension < 7) |
| `urgent-api33` | 10.0.2.18 | yes | yes, then TLS 1.3 | yes (extension < 7) |
| `pixel-api36` | 10.0.2.16 | yes | — | no |
| `pixel-api37` | 10.0.2.17 | yes | yes, then TLS 1.3 | no |

So, as the verdict says, the floor's readings go through the debug address field and `adb forward`,
and NSD is read on the newer images and on the real phones. What the table adds:

- **`urgent-api33` is the emulator for the `MulticastLock`.** It joins the shared Wi-Fi and is below
  T extensions 7, so the rule takes the lock there and its acquire and release can be read in
  `adb logcat`. The emulator cannot show that the lock is *needed*: with the lock off, `urgent-api33`
  still answered `pixel-api36`'s discovery. That half stays with the Redmi in R2.
- **The first connect after a resolve can leave by the wrong interface.** On `urgent-api33` the
  emulator's `eth0` sits on 10.0.2.15/24 beside `wlan0`, and the first connect to the resolved
  10.0.2.16 went out of `eth0` and failed `EHOSTUNREACH`; the next resolve, a few seconds later,
  connected. C connects through the Wi-Fi `Network` the service was found on (`Network.socketFactory`)
  rather than the default route, and retries on the next resolve; a real phone whose default
  network is mobile data has the same shape.
