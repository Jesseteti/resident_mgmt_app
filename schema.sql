-- =========================
-- Residents
-- =========================
CREATE TABLE residents (
    id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT,
    rate_amount NUMERIC(10,2) NOT NULL CHECK (rate_amount > 0),
    rate_frequency TEXT NOT NULL CHECK (rate_frequency IN ('Weekly', 'Monthly')),
    start_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    notes TEXT
);

-- =========================
-- Ledger Entries
-- =========================
CREATE TABLE ledger_entries (
    id SERIAL PRIMARY KEY,
    resident_id INTEGER NOT NULL
        REFERENCES residents(id)
        ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('charge', 'payment', 'adjustment')),
    amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    description TEXT,
    source TEXT
);

-- Prevent duplicate auto rent charges for the same resident on the same date
CREATE UNIQUE INDEX uq_auto_rent_charge
ON ledger_entries (resident_id, entry_date)
WHERE entry_type = 'charge' AND source = 'auto_rent';

-- Helpful index for resident ledger page ordering/filtering
CREATE INDEX idx_ledger_resident_date
ON ledger_entries (resident_id, entry_date, id);
