import { openDB } from 'idb';

const DB_NAME = 'SafeDriveDB';
const STORE_NAME = 'videos';

const dbPromise = openDB(DB_NAME, 1, {
  upgrade(db) {
    db.createObjectStore(STORE_NAME);
  },
});

export const saveVideo = async (key, blob) => {
  const db = await dbPromise;
  await db.put(STORE_NAME, blob, key);
};

export const getVideo = async (key) => {
  const db = await dbPromise;
  return await db.get(STORE_NAME, key);
};

export const deleteVideo = async (key) => {
  const db = await dbPromise;
  await db.delete(STORE_NAME, key);
};

export const clearVideos = async () => {
  const db = await dbPromise;
  await db.clear(STORE_NAME);
};
