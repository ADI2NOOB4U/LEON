# LEON Mobile

An Expo + React Native TypeScript foundation for LEON. It uses Reanimated for UI-thread motion and Skia for the celestial graphics; Three.js is intentionally omitted because the visual system does not need a continuous 3D render loop.

## Run

1. Start the existing FastAPI backend from the repository root.
2. In this directory, copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL` if needed.
3. Run `npm install`, then `npm run android`.

For an Android emulator, the default `http://10.0.2.2:8000` reaches the host machine. A physical device needs the host LAN address.

## Architecture

- `src/lib/api.ts` is the single FastAPI client.
- `src/types/api.ts` mirrors shared task and chat payloads.
- `src/screens` holds the home, tasks, task detail, chat, and connection views.
- `src/components/LeonCore.tsx` keeps animation on the native/UI side and respects Android reduced-motion settings.
