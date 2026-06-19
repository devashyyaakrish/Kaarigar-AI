-- Users (customers + workers)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    role VARCHAR(10) NOT NULL,  -- 'customer' or 'worker'
    name VARCHAR(100),
    language VARCHAR(20) DEFAULT 'hinglish',
    lat FLOAT, lon FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Workers (replaces workers.json)
CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    skills TEXT[],                 -- ['plumbing', 'electrical']
    trust_score FLOAT DEFAULT 5.0,
    jobs_completed INT DEFAULT 0,
    jobs_declined INT DEFAULT 0,
    currently_available BOOLEAN DEFAULT TRUE,
    preferred_radius_km FLOAT DEFAULT 5.0,
    minimum_job_value JSONB DEFAULT '{}',
    specialization_weights JSONB DEFAULT '{}',
    shop_name VARCHAR(100),
    lat FLOAT, lon FLOAT
);

-- Jobs
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES users(id),
    worker_id INT REFERENCES workers(id),
    problem_type VARCHAR(50),
    description TEXT,
    status VARCHAR(30) DEFAULT 'open',
    price_estimate JSONB,
    before_image_url TEXT,
    after_image_url TEXT,
    rating INT,
    review_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Session state per user (replaces your SESSION dict)
CREATE TABLE user_sessions (
    phone VARCHAR(20) PRIMARY KEY,
    state VARCHAR(50) DEFAULT 'idle',  -- 'awaiting_worker_selection', etc.
    context JSONB DEFAULT '{}',        -- stores current_job, matched_workers, etc.
    updated_at TIMESTAMP DEFAULT NOW()
);