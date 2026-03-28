-- Seed: Common injection molding materials
INSERT INTO materials (id, name, family, min_wall_thickness_mm, max_wall_thickness_mm, recommended_draft_deg, shrinkage_pct, melt_temp_c, mold_temp_c) VALUES
('abs_generic',     'ABS (Generic)',           'ABS',  0.75, 3.5, 1.0, 0.5,  230, 60),
('abs_pc',          'ABS/PC Blend',            'ABS',  0.75, 3.5, 1.0, 0.5,  260, 80),
('pp_generic',      'Polypropylene (Generic)',  'PP',   0.65, 3.8, 1.5, 1.5,  230, 40),
('pp_20gf',         'PP 20% Glass Filled',     'PP',   0.75, 3.5, 0.5, 0.4,  250, 60),
('pa6_generic',     'Nylon 6 (Generic)',        'PA',   0.45, 3.0, 0.5, 1.2,  260, 80),
('pa66_33gf',       'Nylon 66 33% GF',         'PA',   0.45, 3.0, 0.25, 0.3, 290, 90),
('pc_generic',      'Polycarbonate (Generic)',  'PC',   1.00, 3.8, 1.0, 0.6,  300, 90),
('pom_generic',     'Acetal/POM (Generic)',     'POM',  0.75, 3.0, 0.5, 2.0,  210, 90),
('pe_hdpe',         'HDPE',                     'PE',   0.75, 4.0, 1.5, 2.5,  230, 40),
('tpu_generic',     'TPU (Generic)',            'TPU',  0.50, 6.0, 3.0, 1.0,  210, 40),
('pbt_generic',     'PBT (Generic)',            'PBT',  0.75, 3.0, 0.5, 1.5,  260, 70),
('ps_generic',      'Polystyrene (Generic)',    'PS',   0.75, 4.0, 1.0, 0.4,  220, 40),
('pmma_generic',    'Acrylic/PMMA (Generic)',   'PMMA', 0.65, 4.0, 1.5, 0.5,  240, 60),
('default',         'Generic Thermoplastic',    'Generic', 0.80, 4.0, 1.0, 1.0, 230, 60);
