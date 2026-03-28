-- MoldMind Initial Schema
-- Phase 1: DFM Analysis Platform

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user', -- user, admin
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects (organizational container)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Parts (uploaded CAD files)
CREATE TABLE parts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_key VARCHAR(512) NOT NULL,        -- S3 key for original STEP file
    mesh_key VARCHAR(512),                 -- S3 key for tessellated mesh (GLB/STL)
    thumbnail_key VARCHAR(512),            -- S3 key for thumbnail image
    file_size_bytes BIGINT,
    units VARCHAR(10) DEFAULT 'mm',        -- mm, inch
    bounding_box JSONB,                    -- {min: [x,y,z], max: [x,y,z]}
    face_count INTEGER,
    volume_mm3 DOUBLE PRECISION,
    surface_area_mm2 DOUBLE PRECISION,
    status VARCHAR(50) DEFAULT 'uploaded', -- uploaded, processing, ready, error
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analysis Jobs
CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_id UUID NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    job_type VARCHAR(50) NOT NULL,         -- dfm_analysis, mold_concept
    status VARCHAR(50) DEFAULT 'queued',   -- queued, processing, completed, failed
    progress SMALLINT DEFAULT 0,           -- 0-100
    pull_direction JSONB,                  -- [x, y, z] unit vector
    material_id VARCHAR(100),              -- material identifier
    parameters JSONB DEFAULT '{}',         -- job-specific parameters
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    worker_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- DFM Analysis Results
CREATE TABLE dfm_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    part_id UUID NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    moldability_score SMALLINT NOT NULL,    -- 0-100
    pull_direction JSONB NOT NULL,          -- [x, y, z]
    summary JSONB NOT NULL,                -- {critical: N, warning: N, info: N}
    metadata JSONB DEFAULT '{}',           -- analysis metadata (timings, versions)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual DFM Issues
CREATE TABLE dfm_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    result_id UUID NOT NULL REFERENCES dfm_results(id) ON DELETE CASCADE,
    rule_id VARCHAR(100) NOT NULL,          -- e.g., 'draft_angle', 'wall_thickness'
    severity VARCHAR(20) NOT NULL,          -- critical, warning, info
    category VARCHAR(50) NOT NULL,          -- draft, thickness, undercut, geometry, gate
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT,                         -- recommended fix
    affected_faces INTEGER[],               -- face indices in tessellated mesh
    affected_region JSONB,                  -- bounding box of affected area
    measured_value DOUBLE PRECISION,        -- actual measured value
    threshold_value DOUBLE PRECISION,       -- rule threshold that was violated
    unit VARCHAR(20),                       -- unit of measured/threshold values
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Trail
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    entity_type VARCHAR(50) NOT NULL,       -- part, analysis, project
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,            -- created, updated, deleted, analyzed
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Materials (reference data)
CREATE TABLE materials (
    id VARCHAR(100) PRIMARY KEY,            -- e.g., 'abs_generic', 'pp_20gf'
    name VARCHAR(255) NOT NULL,
    family VARCHAR(100) NOT NULL,           -- ABS, PP, PA, PC, etc.
    min_wall_thickness_mm DOUBLE PRECISION,
    max_wall_thickness_mm DOUBLE PRECISION,
    recommended_draft_deg DOUBLE PRECISION,
    shrinkage_pct DOUBLE PRECISION,
    melt_temp_c DOUBLE PRECISION,
    mold_temp_c DOUBLE PRECISION,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_parts_project ON parts(project_id);
CREATE INDEX idx_parts_user ON parts(user_id);
CREATE INDEX idx_parts_status ON parts(status);
CREATE INDEX idx_jobs_part ON analysis_jobs(part_id);
CREATE INDEX idx_jobs_status ON analysis_jobs(status);
CREATE INDEX idx_dfm_results_part ON dfm_results(part_id);
CREATE INDEX idx_dfm_issues_result ON dfm_issues(result_id);
CREATE INDEX idx_dfm_issues_severity ON dfm_issues(severity);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);
