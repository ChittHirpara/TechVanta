# BhoomiScan AI (TechVanta) Mobile App

Sovereign Land Record Digitization, Fraud Verification, and Field Audit Mobile Application built with **React Native** and **Expo SDK 54** for the Smart India Hackathon platform.

---

## 🚀 Features

- **Field Officer Authentication**: Role-based access control (`verifier`, `admin`, `field_officer`) backed by JWT tokens stored securely via `expo-secure-store`.
- **Live Ingestion Analytics**: Real-time stats dashboard displaying total ingested records, verified count, pending review queue, flagged attributes count, and district-wise breakdown.
- **Document Camera & Capture**: High-resolution camera scan interface with visual alignment frame and gallery photo selector fallback.
- **Live SSE Extraction Pipeline**: Consumes Server-Sent Events (`/api/v1/documents/{id}/events`) to stream real-time pipeline stages (`OCR Scan → LLM Extraction → Rule Validation → Persistence`).
- **Field Review & Attribute Correction**: Detailed view of extracted land record attributes, confidence scores, flagged states, field correction modal with reason log, and verifier digital signature sealing.
- **Searchable Land Registry**: Search land records by Khasra number, plot title, owner name, status filter, or district filter.
- **Cryptographic Audit Trail**: Complete event chronology with SHA-256 integrity hash verification.

---

## 🛠️ Tech Stack & SDK Version

- **Framework**: Expo SDK 54 (React Native 0.81.5 / React 19.1.0)
- **Navigation**: React Navigation (Native Stack)
- **Storage**: `expo-secure-store`
- **Camera & Gallery**: `expo-camera`, `expo-image-picker`
- **Streaming**: `react-native-sse`
- **Design System**: BhoomiScan Sovereign Government Theme Tokens (`src/theme/theme.js`)

---

## 📋 Prerequisites & Setup

### 1. Installation

From the `mobile/` directory, install all required dependencies:

```bash
cd mobile
npm install --legacy-peer-deps
```

### 2. Environment Configuration

The application reads the API base URL from `EXPO_PUBLIC_API_BASE_URL` in `mobile/.env`.

Default `.env` configuration:

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

> ⚠️ **Important for Physical Device Testing (iOS / Android)**:  
> When testing on a physical mobile device running the Expo Go app or a standalone build, `localhost` points to the mobile device itself. You **must** replace `localhost` with your development computer's local network (LAN) IP address:
>
> ```env
> EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000/api/v1
> ```

---

## 🏃 Running the Application

Start the Expo development server:

```bash
npx expo start
```

- Press `a` to open in Android Emulator
- Press `i` to open in iOS Simulator
- Press `w` to launch in Web browser
- Scan the QR code using **Expo Go** on your physical phone

---

## 🧪 Health Verification

To verify Expo SDK package version alignment:

```bash
npx expo-doctor
```

Expected result: `18/18 checks passed. No issues detected!`

---

## 🏛️ Default Test Credentials

| Role | Username | Password |
| :--- | :--- | :--- |
| **Verifying Officer** | `verifier` | `verifier123` |
| **Administrator** | `admin` | `admin123` |
| **Field Officer** | `field_officer` | `officer123` |
