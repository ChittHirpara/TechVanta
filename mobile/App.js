import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';
import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from './src/context/AuthContext';
import { I18nProvider } from './src/i18n/i18n';
import { initAutoSyncEngine } from './src/services/syncEngine';
import AppNavigator from './src/navigation/AppNavigator';

function App() {
  useEffect(() => {
    const unsub = initAutoSyncEngine();
    return () => {
      if (typeof unsub === 'function') unsub();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <I18nProvider>
        <AuthProvider>
          <StatusBar style="light" backgroundColor="#0b1f3a" />
          <AppNavigator />
        </AuthProvider>
      </I18nProvider>
    </SafeAreaProvider>
  );
}

registerRootComponent(App);

