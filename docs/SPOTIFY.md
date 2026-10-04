# Spotify in LEON

LEON uses Spotify's official Web Playback SDK as its primary in-browser
Spotify Connect device. The browser loads the SDK from
`https://sdk.scdn.co/spotify-player.js`; LEON does not download, transform, or
capture Spotify audio.

## Local setup

1. Create a Spotify app in the Spotify Developer Dashboard.
2. Put the client ID and secret in `backend/.env` only:

   ```dotenv
   SPOTIFY_CLIENT_ID=your-client-id
   SPOTIFY_CLIENT_SECRET=your-client-secret
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/media/spotify/callback
   FRONTEND_BASE_URL=http://127.0.0.1:5174
   ```

3. Register this exact redirect URI in the Spotify app settings:

   `http://127.0.0.1:8000/api/media/spotify/callback`

   Spotify requires an exact match. Use the explicit loopback address
   `127.0.0.1`; `localhost` is not a valid replacement.
4. Start the backend and frontend, open Media, choose **Authorize Spotify**,
   then choose **Enable LEON Player** after returning from Spotify.

LEON requests only the scopes needed for this integration:

- `streaming` for Web Playback SDK browser playback
- `user-read-private` for account/product eligibility
- `user-read-playback-state` for current playback verification
- `user-modify-playback-state` for play, pause, resume, next, previous, and
  transfer commands

The refresh token is stored by the backend in `data/spotify_tokens.json` and
is never sent to the browser. The SDK receives a short-lived access token from
`GET /api/media/spotify/token`. The browser device ID comes only from the SDK
`ready` event and is runtime-only because Spotify device IDs can change.

## Troubleshooting

- `SPOTIFY_REDIRECT_URI_MISMATCH`: the dashboard value and
  `SPOTIFY_REDIRECT_URI` differ; copy the exact value above.
- `PREMIUM_REQUIRED`: the authenticated Spotify account is not eligible for
  Web Playback SDK playback.
- `SPOTIFY_AUTH_REQUIRED`: reconnect Spotify; the backend could not refresh
  the stored authorization.
- `SPOTIFY_DEVICE_UNAVAILABLE` or `SPOTIFY_SDK_NOT_READY`: return to Media and
  enable/retry the LEON Player.
- `AUTOPLAY_BLOCKED`: click **Enable LEON Player** in the browser. Audio is not
  reported as ready until the browser activation and SDK `ready` event occur.

