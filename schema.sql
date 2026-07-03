-- ============================================================
-- COSTOS PRO — Schema relacional completo
-- 35 tablas · query_db directo · SQLite3
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. NÚCLEO: usuarios, empresas, períodos
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'analyst',  -- admin | analyst | readonly
    reset_token TEXT,
    reset_token_expiry DATETIME,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    business_name TEXT NOT NULL,
    trade_name TEXT,
    ruc TEXT,
    sector TEXT NOT NULL,         -- manufactura | textil | restaurante | salud | servicios | comercio | educacion | otro
    subsector TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    currency TEXT DEFAULT 'PEN',
    igv_rate REAL DEFAULT 0.18,
    active_period_id INTEGER,
    logo_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    name TEXT NOT NULL,           -- "Enero 2025", "2025-I", "Anual 2025"
    period_type TEXT DEFAULT 'monthly', -- monthly | quarterly | semiannual | annual
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active INTEGER DEFAULT 0,
    is_closed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- ============================================================
-- 2. MAESTROS: unidades, departamentos, cargos
-- ============================================================

CREATE TABLE IF NOT EXISTS units_of_measure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,               -- peso | volumen | longitud | tiempo | unidad | otro
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    department_id INTEGER,
    labor_type TEXT DEFAULT 'MOD', -- MOD | MOI | admin | ventas
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- ============================================================
-- 3. PERSONAL Y MANO DE OBRA
-- ============================================================

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    dni TEXT,
    full_name TEXT NOT NULL,
    position_id INTEGER,
    department_id INTEGER,
    contract_type TEXT DEFAULT 'indefinido', -- indefinido | plazo_fijo | locacion | practicante
    start_date DATE,
    end_date DATE,
    is_active INTEGER DEFAULT 1,
    in_payroll INTEGER DEFAULT 1,
    -- Remuneraciones
    basic_salary REAL DEFAULT 0,
    bonus REAL DEFAULT 0,
    family_allowance REAL DEFAULT 0,
    gratification_monthly REAL DEFAULT 0,   -- gratificación mensualizada
    cts_monthly REAL DEFAULT 0,             -- CTS mensualizada
    essalud REAL DEFAULT 0,
    sctr REAL DEFAULT 0,
    other_benefits REAL DEFAULT 0,
    total_monthly_cost REAL DEFAULT 0,
    -- Horas
    available_hours_month REAL DEFAULT 192,
    assigned_hours_month REAL DEFAULT 0,
    cost_per_hour REAL DEFAULT 0,
    -- Clasificación
    labor_type TEXT DEFAULT 'MOD',          -- MOD | MOI | admin | ventas
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES positions(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- ============================================================
-- 4. PRODUCTOS Y SERVICIOS
-- ============================================================

CREATE TABLE IF NOT EXISTS products_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,               -- producto | servicio | semielaborado | materia_prima
    unit_id INTEGER,
    sale_price REAL DEFAULT 0,
    standard_cost REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES units_of_measure(id)
);

-- ============================================================
-- 5. RECURSOS (ABC - Nivel 1)
-- ============================================================

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,               -- energia | personal | depreciacion | materiales | servicios | otros
    annual_amount REAL DEFAULT 0,
    monthly_amount REAL DEFAULT 0,
    driver_type TEXT,            -- Kw-h | m3 | horas | metros | unidades | porcentaje
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, period_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

-- ============================================================
-- 6. CENTROS DE ACTIVIDAD (ABC - Nivel 2)
-- ============================================================

CREATE TABLE IF NOT EXISTS activity_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    center_type TEXT DEFAULT 'operativo', -- estrategico | operativo | apoyo
    total_cost_annual REAL DEFAULT 0,
    total_cost_monthly REAL DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, period_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

-- ============================================================
-- 7. ACTIVIDADES (ABC - Nivel 3)
-- ============================================================

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    center_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    driver_type TEXT,            -- tipo de inductor para distribuir a objetos
    driver_total REAL DEFAULT 0, -- total del inductor
    total_cost REAL DEFAULT 0,   -- costo asignado a esta actividad
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (center_id) REFERENCES activity_centers(id) ON DELETE CASCADE
);

-- ============================================================
-- 8. OBJETOS DE COSTO (ABC - Nivel 4)
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    product_id INTEGER,          -- FK a products_services si aplica
    quantity_month REAL DEFAULT 0,
    unit_cost_abc REAL DEFAULT 0,
    unit_cost_traditional REAL DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, period_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id),
    FOREIGN KEY (product_id) REFERENCES products_services(id)
);

-- ============================================================
-- 9. MODELOS ABC + DISTRIBUCIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS abc_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sector TEXT,
    status TEXT DEFAULT 'borrador', -- borrador | calculado | aprobado
    admin_expense REAL DEFAULT 0,
    sales_expense REAL DEFAULT 0,
    financial_expense REAL DEFAULT 0,
    desired_margin REAL DEFAULT 0,
    calculated_at DATETIME,
    calculated_by INTEGER,
    image_path TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id),
    FOREIGN KEY (calculated_by) REFERENCES users(id)
);

-- Nivel 1→2: Recurso → Centro de Actividad
CREATE TABLE IF NOT EXISTS abc_resource_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abc_model_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    center_id INTEGER NOT NULL,
    driver_quantity REAL DEFAULT 0,   -- cantidad del inductor para este centro
    driver_percentage REAL DEFAULT 0, -- % del total del inductor
    allocated_amount REAL DEFAULT 0,  -- monto asignado
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(abc_model_id, resource_id, center_id),
    FOREIGN KEY (abc_model_id) REFERENCES abc_models(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (center_id) REFERENCES activity_centers(id)
);

-- Nivel 2→3: Centro de Actividad → Actividad
CREATE TABLE IF NOT EXISTS abc_center_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abc_model_id INTEGER NOT NULL,
    center_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    driver_quantity REAL DEFAULT 0,
    driver_percentage REAL DEFAULT 0,
    allocated_amount REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(abc_model_id, center_id, activity_id),
    FOREIGN KEY (abc_model_id) REFERENCES abc_models(id) ON DELETE CASCADE,
    FOREIGN KEY (center_id) REFERENCES activity_centers(id),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);

-- Nivel 3→4: Actividad → Objeto de Costo
CREATE TABLE IF NOT EXISTS abc_object_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abc_model_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    cost_object_id INTEGER NOT NULL,
    driver_quantity REAL DEFAULT 0,
    driver_percentage REAL DEFAULT 0,
    allocated_amount REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(abc_model_id, activity_id, cost_object_id),
    FOREIGN KEY (abc_model_id) REFERENCES abc_models(id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activities(id),
    FOREIGN KEY (cost_object_id) REFERENCES cost_objects(id)
);

-- Resultados finales ABC por objeto de costo
CREATE TABLE IF NOT EXISTS abc_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abc_model_id INTEGER NOT NULL,
    cost_object_id INTEGER NOT NULL,
    production_cost REAL DEFAULT 0,
    admin_expense_allocated REAL DEFAULT 0,
    sales_expense_allocated REAL DEFAULT 0,
    financial_expense_allocated REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    margin_amount REAL DEFAULT 0,
    sale_value REAL DEFAULT 0,
    igv_amount REAL DEFAULT 0,
    sale_price REAL DEFAULT 0,
    unit_cost_abc REAL DEFAULT 0,
    unit_cost_traditional REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(abc_model_id, cost_object_id),
    FOREIGN KEY (abc_model_id) REFERENCES abc_models(id) ON DELETE CASCADE,
    FOREIGN KEY (cost_object_id) REFERENCES cost_objects(id)
);

-- ============================================================
-- 10. COSTOS POR PROCESO
-- ============================================================

CREATE TABLE IF NOT EXISTS process_cost_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    model_type TEXT NOT NULL,    -- normal | agregadas | perdidas | protecho
    product_name TEXT,
    status TEXT DEFAULT 'borrador',
    calculated_at DATETIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

CREATE TABLE IF NOT EXISTS process_departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    dept_order INTEGER NOT NULL,  -- secuencia del departamento
    name TEXT NOT NULL,
    -- Flujo físico
    uiipp REAL DEFAULT 0,        -- unidades iniciales en proceso
    uprod REAL DEFAULT 0,        -- unidades iniciadas/recibidas
    uag REAL DEFAULT 0,          -- unidades agregadas
    utt REAL DEFAULT 0,          -- unidades transferidas terminadas
    utnt REAL DEFAULT 0,         -- terminadas no transferidas
    uifpp REAL DEFAULT 0,        -- unidades finales en proceso
    up REAL DEFAULT 0,           -- unidades perdidas
    -- Grado de avance
    mat_pct_uiipp REAL DEFAULT 0,   -- % avance materiales UIIPP
    conv_pct_uiipp REAL DEFAULT 0,  -- % avance conversión UIIPP
    mat_pct_uifpp REAL DEFAULT 0,   -- % avance materiales UIFPP
    conv_pct_uifpp REAL DEFAULT 0,  -- % avance conversión UIFPP
    -- Costos
    cost_mat_prior REAL DEFAULT 0,  -- costo materiales período anterior
    cost_conv_prior REAL DEFAULT 0, -- costo conversión período anterior
    cost_transfer_in REAL DEFAULT 0,-- costo transferido del dpto anterior
    cost_mat_current REAL DEFAULT 0,-- materiales período actual
    cost_mod_current REAL DEFAULT 0,-- MOD período actual
    cost_cif_current REAL DEFAULT 0,-- CIF período actual
    -- Resultados calculados
    ue_mat REAL DEFAULT 0,       -- unidades equivalentes materiales
    ue_conv REAL DEFAULT 0,      -- unidades equivalentes conversión
    cu_mat REAL DEFAULT 0,       -- costo unitario materiales
    cu_conv REAL DEFAULT 0,      -- costo unitario conversión
    cu_total REAL DEFAULT 0,     -- costo unitario total
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES process_cost_models(id) ON DELETE CASCADE
);

-- ============================================================
-- 11. PRESUPUESTOS
-- ============================================================

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'borrador',
    -- Totales calculados
    total_sales REAL DEFAULT 0,
    total_production_cost REAL DEFAULT 0,
    total_operating_expenses REAL DEFAULT 0,
    gross_profit REAL DEFAULT 0,
    net_income REAL DEFAULT 0,
    total_investment REAL DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

CREATE TABLE IF NOT EXISTS budget_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name TEXT NOT NULL,
    unit_id INTEGER,
    month INTEGER,               -- 1-12
    quantity REAL DEFAULT 0,
    unit_price REAL DEFAULT 0,
    total_sales REAL DEFAULT 0,
    growth_rate REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products_services(id),
    FOREIGN KEY (unit_id) REFERENCES units_of_measure(id)
);

CREATE TABLE IF NOT EXISTS budget_production (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name TEXT NOT NULL,
    month INTEGER,
    sales_units REAL DEFAULT 0,
    ending_inventory REAL DEFAULT 0,
    beginning_inventory REAL DEFAULT 0,
    required_production REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products_services(id)
);

CREATE TABLE IF NOT EXISTS budget_labor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    employee_id INTEGER,
    position_name TEXT NOT NULL,
    labor_type TEXT DEFAULT 'MOD',
    month INTEGER,
    hours_required REAL DEFAULT 0,
    cost_per_hour REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS budget_cif (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    concept TEXT NOT NULL,
    cif_type TEXT DEFAULT 'fijo',  -- fijo | variable
    month INTEGER,
    amount REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS budget_cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    month INTEGER NOT NULL,       -- 0=inicial, 1-12=meses
    -- Ingresos
    cash_sales REAL DEFAULT 0,
    collections REAL DEFAULT 0,
    other_income REAL DEFAULT 0,
    total_income REAL DEFAULT 0,
    -- Egresos operativos
    raw_materials REAL DEFAULT 0,
    labor REAL DEFAULT 0,
    cif_cash REAL DEFAULT 0,
    admin_expenses REAL DEFAULT 0,
    sales_expenses REAL DEFAULT 0,
    -- Egresos financieros
    loan_principal REAL DEFAULT 0,
    loan_interest REAL DEFAULT 0,
    -- Inversión
    investment REAL DEFAULT 0,
    total_outflow REAL DEFAULT 0,
    -- Saldos
    net_cashflow REAL DEFAULT 0,
    beginning_balance REAL DEFAULT 0,
    ending_balance REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS budget_debt_service (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id INTEGER NOT NULL,
    concept TEXT NOT NULL,
    loan_amount REAL DEFAULT 0,
    annual_rate REAL DEFAULT 0,
    months INTEGER DEFAULT 12,
    month INTEGER,
    principal REAL DEFAULT 0,
    interest REAL DEFAULT 0,
    fee REAL DEFAULT 0,
    balance REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
);

-- ============================================================
-- 12. COSTOS DE CALIDAD
-- ============================================================

CREATE TABLE IF NOT EXISTS quality_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    activity_name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,      -- prevencion | evaluacion | falla_interna | falla_externa | no_aplica
    responsible TEXT,
    monthly_cost REAL DEFAULT 0,
    annual_cost REAL DEFAULT 0,
    pct_of_sales REAL DEFAULT 0,
    ai_classified INTEGER DEFAULT 0,  -- 1 si fue clasificado por IA
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

-- ============================================================
-- 13. INVENTARIO Y KARDEX (mejorado del v4)
-- ============================================================

CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    product_id INTEGER,          -- FK a products_services si es un producto
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'insumo', -- insumo | producto | semielaborado | activo
    unit_id INTEGER,
    current_stock REAL DEFAULT 0,
    min_stock REAL DEFAULT 0,
    max_stock REAL DEFAULT 0,
    average_cost REAL DEFAULT 0,
    last_purchase_cost REAL DEFAULT 0,
    valuation_method TEXT DEFAULT 'promedio', -- promedio | peps
    safety_stock REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products_services(id),
    FOREIGN KEY (unit_id) REFERENCES units_of_measure(id)
);

CREATE TABLE IF NOT EXISTS kardex_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_item_id INTEGER NOT NULL,
    movement_date DATE NOT NULL,
    movement_type TEXT NOT NULL,  -- entrada | salida | devolucion | ajuste
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    stock_after REAL,
    average_cost_after REAL,
    reference TEXT,
    document_type TEXT,           -- OC | OP | guia | factura | ajuste
    document_number TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE CASCADE
);

-- ============================================================
-- 14. ESTRUCTURA DE COSTOS (mejorada del v4)
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_structures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_id INTEGER,
    name TEXT NOT NULL,
    product_id INTEGER,
    product_service TEXT,
    structure_date DATE,
    status TEXT DEFAULT 'borrador',
    origin TEXT DEFAULT 'manual',  -- manual | abc | proceso | importado
    monthly_production REAL,
    sale_price REAL,
    igv_rate REAL DEFAULT 0.18,
    desired_margin REAL,
    source_abc_model_id INTEGER,
    source_process_model_id INTEGER,
    image_path TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id),
    FOREIGN KEY (product_id) REFERENCES products_services(id),
    FOREIGN KEY (source_abc_model_id) REFERENCES abc_models(id),
    FOREIGN KEY (source_process_model_id) REFERENCES process_cost_models(id)
);

CREATE TABLE IF NOT EXISTS cost_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_id INTEGER NOT NULL,
    parent_id INTEGER,
    name TEXT NOT NULL,
    category_type TEXT,          -- mp | mod | cif | gasto_admin | gasto_ventas | gasto_financiero
    order_index INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (structure_id) REFERENCES cost_structures(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES cost_categories(id)
);

CREATE TABLE IF NOT EXISTS cost_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    resource_id INTEGER,          -- FK a resources si viene del ABC
    employee_id INTEGER,          -- FK a employees si es MOD
    inventory_item_id INTEGER,    -- FK a inventory si es MP
    code TEXT,
    description TEXT NOT NULL,
    cost_type TEXT DEFAULT 'variable', -- fijo | variable | semivariable
    unit TEXT,
    quantity REAL DEFAULT 0,
    unit_cost REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    source_cost TEXT DEFAULT 'manual',
    cost_driver TEXT,
    notes TEXT,
    order_index INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES cost_categories(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
);

-- ============================================================
-- 15. ASIGNACIÓN EMPLEADOS ↔ ACTIVIDADES
-- ============================================================

CREATE TABLE IF NOT EXISTS employee_activity_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    assignment_pct REAL DEFAULT 0,  -- % de tiempo asignado a esta actividad
    hours_assigned REAL DEFAULT 0,
    cost_assigned REAL DEFAULT 0,
    period_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, activity_id, period_id),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

-- ============================================================
-- 16. IA: conversaciones y contexto
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_id INTEGER,
    period_id INTEGER,
    agent_type TEXT DEFAULT 'general', -- general | estructura | clasificador | calidad | presupuestos | abc | proceso | graficos | reportes | manual
    module_context TEXT,          -- módulo donde se inició la conversación
    session_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (period_id) REFERENCES periods(id)
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,           -- user | assistant
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
);

-- ============================================================
-- 17. PLANTILLAS DE SECTOR
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,           -- NULL = plantilla global del sistema
    name TEXT NOT NULL,
    sector TEXT,
    description TEXT,
    template_type TEXT DEFAULT 'abc', -- abc | proceso | presupuesto | estructura
    json_data TEXT,
    is_global INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ============================================================
-- 18. AUDITORÍA Y PRECIOS
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_id INTEGER,
    entity_type TEXT,
    entity_id INTEGER,
    action TEXT,                  -- create | update | delete | calculate | export
    module TEXT,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS price_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    unit TEXT,
    suggested_price REAL,
    source_url TEXT,
    source_name TEXT,
    query_date DATETIME,
    accepted INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ============================================================
-- ÍNDICES para performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id);
CREATE INDEX IF NOT EXISTS idx_periods_company ON periods(company_id);
CREATE INDEX IF NOT EXISTS idx_employees_company ON employees(company_id);
CREATE INDEX IF NOT EXISTS idx_resources_company_period ON resources(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_activity_centers_company ON activity_centers(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_activities_center ON activities(center_id);
CREATE INDEX IF NOT EXISTS idx_cost_objects_company ON cost_objects(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_abc_models_company ON abc_models(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_kardex_item ON kardex_movements(inventory_item_id, movement_date);
CREATE INDEX IF NOT EXISTS idx_quality_costs_company ON quality_costs(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_budgets_company ON budgets(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_messages_conv ON ai_messages(conversation_id);

-- Usuarios por empresa con roles y permisos por módulo
CREATE TABLE IF NOT EXISTS company_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'viewer',
    modules TEXT DEFAULT 'all',
    invited_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(company_id, user_id)
);
