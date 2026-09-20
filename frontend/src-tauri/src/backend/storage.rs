use crate::backend::model::ForwardProfile;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
struct Settings {
    version: u32,
    favorites: Vec<ForwardProfile>,
    #[serde(default)]
    preferences: serde_json::Value,
}

pub struct ProfileStore {
    path: PathBuf,
    favorites: Vec<ForwardProfile>,
    preferences: serde_json::Value,
    load_failed: bool,
}

impl ProfileStore {
    pub fn new(path: PathBuf) -> Self {
        Self {
            path,
            favorites: Vec::new(),
            preferences: serde_json::json!({}),
            load_failed: false,
        }
    }
    pub fn favorites(&self) -> &[ForwardProfile] {
        &self.favorites
    }

    pub fn load(&mut self) -> Result<(), String> {
        if !self.path.exists() {
            return Ok(());
        }
        let bytes = fs::read(&self.path).map_err(|e| {
            self.load_failed = true;
            e.to_string()
        })?;
        let raw: serde_json::Value = serde_json::from_slice(&bytes).map_err(|e| {
            self.load_failed = true;
            format!("invalid settings: {e}")
        })?;
        let favorites = raw.get("favorites").ok_or_else(|| {
            self.load_failed = true;
            "favorites is missing".to_string()
        })?;
        let items = favorites.as_array().ok_or_else(|| {
            self.load_failed = true;
            "favorites must be an array".to_string()
        })?;
        let mut seen = std::collections::HashSet::new();
        self.favorites = items
            .iter()
            .filter_map(|item| serde_json::from_value::<ForwardProfile>(item.clone()).ok())
            .filter(|item| item.validate().is_ok() && seen.insert(item.id.clone()))
            .collect();
        self.preferences = raw
            .get("preferences")
            .cloned()
            .unwrap_or_else(|| serde_json::json!({}));
        self.load_failed = false;
        Ok(())
    }

    pub fn upsert(&mut self, profile: ForwardProfile) -> Result<(), String> {
        profile.validate()?;
        if self.load_failed {
            return Err("settings load failed; refusing to overwrite".into());
        }
        let old = self.favorites.clone();
        if let Some(item) = self.favorites.iter_mut().find(|item| item.id == profile.id) {
            *item = profile;
        } else {
            self.favorites.push(profile);
        }
        if let Err(error) = self.save() {
            self.favorites = old;
            return Err(error);
        }
        Ok(())
    }

    pub fn delete(&mut self, id: &str) -> Result<(), String> {
        if self.load_failed {
            return Err("settings load failed; refusing to overwrite".into());
        }
        let old = self.favorites.clone();
        self.favorites.retain(|item| item.id != id);
        if let Err(error) = self.save() {
            self.favorites = old;
            return Err(error);
        }
        Ok(())
    }

    fn save(&self) -> Result<(), String> {
        let payload = serde_json::to_vec_pretty(&Settings {
            version: 1,
            favorites: self.favorites.clone(),
            preferences: self.preferences.clone(),
        })
        .map_err(|e| e.to_string())?;
        let temporary = self.path.with_extension("json.tmp");
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        fs::write(&temporary, payload).map_err(|e| e.to_string())?;
        fs::rename(&temporary, &self.path).map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::ProfileStore;
    use crate::backend::model::ForwardProfile;
    use serde_json::json;
    use std::fs;

    fn profile() -> ForwardProfile {
        ForwardProfile::new("API", "gateway", 9000, "api.internal", 443)
    }

    #[test]
    fn round_trips_updates_and_deletes_a_favorite() {
        let path = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-storage-{}.json",
            uuid::Uuid::new_v4()
        ));
        let mut store = ProfileStore::new(path.clone());
        let mut item = profile();
        store.upsert(item.clone()).unwrap();
        item.local_port = 9001;
        store.upsert(item.clone()).unwrap();
        let mut loaded = ProfileStore::new(path.clone());
        loaded.load().unwrap();
        assert_eq!(loaded.favorites().len(), 1);
        assert_eq!(loaded.favorites()[0].local_port, 9001);
        loaded.delete(&item.id).unwrap();
        assert!(loaded.favorites().is_empty());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn rejects_corrupt_json_without_overwriting_it() {
        let path = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-corrupt-{}.json",
            uuid::Uuid::new_v4()
        ));
        fs::write(&path, "not-json").unwrap();
        let mut store = ProfileStore::new(path.clone());
        assert!(store.load().is_err());
        assert!(store.upsert(profile()).is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "not-json");
        let _ = fs::remove_file(path);
    }

    #[test]
    fn skips_invalid_items_and_duplicate_ids() {
        let path = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-items-{}.json",
            uuid::Uuid::new_v4()
        ));
        let item = profile();
        let payload = json!({"favorites": [item.clone(), item, {"name": "missing"}]});
        fs::write(&path, serde_json::to_vec(&payload).unwrap()).unwrap();
        let mut store = ProfileStore::new(path.clone());
        store.load().unwrap();
        assert_eq!(store.favorites().len(), 1);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn preserves_preferences_when_updating_favorites() {
        let path = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-preferences-{}.json",
            uuid::Uuid::new_v4()
        ));
        let item = profile();
        let payload = json!({"version": 1, "favorites": [], "preferences": {"confirmOnExit": false, "defaultLocalBind": "::1"}});
        fs::write(&path, serde_json::to_vec(&payload).unwrap()).unwrap();
        let mut store = ProfileStore::new(path.clone());
        store.load().unwrap();
        store.upsert(item).unwrap();
        let saved: serde_json::Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(saved["preferences"]["confirmOnExit"], false);
        assert_eq!(saved["preferences"]["defaultLocalBind"], "::1");
        let _ = fs::remove_file(path);
    }
}
