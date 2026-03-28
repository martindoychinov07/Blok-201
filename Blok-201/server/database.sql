DROP TABLE IF EXISTS health_records;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('USER', 'CAREGIVER')),
    full_name VARCHAR(100),
    dementia_stage INT CHECK (dementia_stage IN (1, 2)),
    patient_id UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE health_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    transcript TEXT,
    ai_sentiment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);