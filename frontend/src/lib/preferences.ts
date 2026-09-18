export type DefaultLocalBind = "127.0.0.1" | "0.0.0.0" | "::1";

export interface AppPreferences {
  confirmOnExit: boolean;
  defaultLocalBind: DefaultLocalBind;
  autoSelectPort: boolean;
}

export const DEFAULT_PREFERENCES: AppPreferences = {
  confirmOnExit: true,
  defaultLocalBind: "127.0.0.1",
  autoSelectPort: false,
};

const STORAGE_KEY = "ssh-forwarder.preferences";

export function readPreferences(): AppPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    const parsed = JSON.parse(raw) as Partial<AppPreferences>;
    const defaultLocalBind = parsed.defaultLocalBind;
    return {
      confirmOnExit: parsed.confirmOnExit !== false,
      defaultLocalBind: defaultLocalBind === "0.0.0.0" || defaultLocalBind === "::1" ? defaultLocalBind : "127.0.0.1",
      autoSelectPort: parsed.autoSelectPort === true,
    };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function writePreferences(preferences: AppPreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Preferences are best effort; a restricted WebView storage must not block the app.
  }
}
