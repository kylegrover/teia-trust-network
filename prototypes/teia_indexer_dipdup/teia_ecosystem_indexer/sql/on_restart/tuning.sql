-- Tuning for a 1-2GB SQLite database on modern hardware
-- These pragmas optimize for speed by leveraging RAM (Memory-Mapped I/O)

-- WAL mode is usually on, but let's ensure it for concurrent read performance
PRAGMA journal_mode = WAL;

-- Synchronous NORMAL is safe in WAL mode and much faster than FULL
PRAGMA synchronous = NORMAL;

-- Set cache to ~256MB (64000 pages * 4KB)
PRAGMA cache_size = -64000;

-- Memory-Map the entire database (up to 2GB) 
-- This makes everything essentially "in-memory" for the OS
PRAGMA mmap_size = 2147483648;

-- Optimize the database on close
PRAGMA optimize;
