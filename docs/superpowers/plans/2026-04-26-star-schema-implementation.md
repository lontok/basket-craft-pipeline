# Star Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Kimball star schema in dbt for Maya (head of merchandising) — three new mart models plus one intermediate, with full schema and singular tests, deployed to `BASKET_CRAFT.ANALYTICS` in Snowflake.

**Architecture:** Four new models layered on top of the existing staging layer. `int_order_items_with_refunds` (view) joins line items to refund totals. `dim_product` (table) and `dim_date` (table, generated from a Snowflake `GENERATOR` spine) are the dimensions. `fct_order_items` (table) is the fact at order line-item grain, with role-playing `dim_product` for both line product and order's primary product.

**Tech Stack:** dbt-core 1.11.8, dbt-snowflake 1.11.4, Snowflake (database `BASKET_CRAFT`, schemas `RAW` and `ANALYTICS`), Python 3.11 venv (existing).

**Reference spec:** `docs/superpowers/specs/2026-04-26-star-schema-design.md`

---

## File Structure

### New files

| Path | Purpose |
|---|---|
| `dbt/models/intermediate/int_order_items_with_refunds.sql` | View: line items joined to refund totals |
| `dbt/models/intermediate/_intermediate.yml` | Schema tests for the intermediate model |
| `dbt/models/marts/dim_product.sql` | Product dimension table |
| `dbt/models/marts/dim_date.sql` | Generated calendar dimension |
| `dbt/models/marts/fct_order_items.sql` | Fact table at order line-item grain |
| `dbt/tests/assert_refund_not_exceeds_price.sql` | Singular test: refund ≤ price per row |
| `dbt/tests/assert_refund_amount_not_negative.sql` | Singular test: refund ≥ 0 |
| `dbt/tests/assert_one_primary_item_per_order.sql` | Singular test: 1 primary item per order |
| `dbt/tests/assert_fct_rowcount_matches_stg.sql` | Singular test: fact row count = stg_order_items row count |

### Modified files

| Path | Change |
|---|---|
| `dbt/models/marts/_models.yml` | Rename to `_marts.yml`; expand to cover all four mart-layer models |
| `dbt/models/marts/monthly_sales_summary.sql` | Add deprecation header comment (final task) |

---

## Per-Task Pre-Flight (run once at the start of every session)

Every dbt command in this plan requires the venv activated, `.env` sourced, and `DBT_PROFILES_DIR` exported. If the shell loses state between commands (it does — Bash tool calls don't persist environment), re-run this prefix before any dbt invocation:

```bash
cd /Users/greglontok/isba-4715/basket-craft-pipeline && \
source venv/bin/activate && \
set -a && source .env && set +a && \
export DBT_PROFILES_DIR="$(pwd)/dbt"
```

Treat each task's `dbt` commands as if prefixed by the above, even when not shown explicitly.

---

## Task 1: Set up `intermediate/` directory and rename `_models.yml` → `_marts.yml`

**Goal:** Establish folder layout and consolidate mart-layer schema tests in one file. Pure scaffolding; no SQL changes yet.

**Files:**
- Create: `dbt/models/intermediate/` (directory)
- Modify: `dbt/models/marts/_models.yml` → rename to `dbt/models/marts/_marts.yml`

- [ ] **Step 1: Create the intermediate directory**

```bash
mkdir -p /Users/greglontok/isba-4715/basket-craft-pipeline/dbt/models/intermediate
```

- [ ] **Step 2: Rename `_models.yml` to `_marts.yml`**

```bash
git mv /Users/greglontok/isba-4715/basket-craft-pipeline/dbt/models/marts/_models.yml \
        /Users/greglontok/isba-4715/basket-craft-pipeline/dbt/models/marts/_marts.yml
```

- [ ] **Step 3: Verify `dbt parse` still works**

Run (with pre-flight prefix):
```bash
cd dbt && dbt parse
```
Expected: no errors, "Performance info" line printed.

- [ ] **Step 4: Commit**

```bash
git add dbt/models/intermediate dbt/models/marts/_marts.yml
git commit -m "Add intermediate model directory; rename _models.yml to _marts.yml"
```

---

## Task 2: Build `dim_date`

**Goal:** Generated 30-year date spine. No source dependencies, so this is the safest first model.

**Files:**
- Create: `dbt/models/marts/dim_date.sql`
- Modify: `dbt/models/marts/_marts.yml` — add tests for `dim_date`

- [ ] **Step 1: Write the model SQL**

Write to `dbt/models/marts/dim_date.sql`:

```sql
{{ config(materialized='table') }}

with date_spine as (
    select dateadd(day, seq4(), '2010-01-01'::date)::date as full_date
    from table(generator(rowcount => 11000))
)

select
    full_date as date_key,
    full_date,
    year(full_date) as year,
    quarter(full_date) as quarter,
    month(full_date) as month,
    monthname(full_date) as month_name,
    day(full_date) as day_of_month,
    dayofweek(full_date) as day_of_week,
    dayname(full_date) as day_name,
    iff(dayofweek(full_date) in (0, 6), true, false) as is_weekend
from date_spine
```

Note: Snowflake's `dayofweek()` returns 0=Sunday through 6=Saturday by default.

- [ ] **Step 2: Add schema tests to `_marts.yml`**

Read the current `dbt/models/marts/_marts.yml`. Add the following YAML block under the existing `models:` list (preserve any existing entries like `monthly_sales_summary`):

```yaml
  - name: dim_date
    description: Conformed calendar dimension. Generated from a 30-year spine starting 2010-01-01.
    columns:
      - name: date_key
        description: Primary key. Type DATE.
        data_tests:
          - unique
          - not_null
      - name: full_date
        description: Duplicate of date_key for query readability.
        data_tests:
          - not_null
      - name: year
        data_tests:
          - not_null
      - name: quarter
        data_tests:
          - not_null
      - name: month
        data_tests:
          - not_null
      - name: is_weekend
        data_tests:
          - accepted_values:
              values: [true, false]
```

- [ ] **Step 3: Build the model and run its tests**

Run (with pre-flight prefix):
```bash
cd dbt && dbt build --select dim_date
```
Expected output: `Done. PASS=N WARN=0 ERROR=0 SKIP=0`, where N includes the model build (1) plus its tests (≥6).

- [ ] **Step 4: Sanity-check the row count**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*), MIN(date_key), MAX(date_key) FROM ANALYTICS.dim_date')
print(cur.fetchone())
cur.close(); conn.close()
"
```
Expected: `(11000, datetime.date(2010, 1, 1), datetime.date(2040, ...))` — confirms 11k rows from 2010-01-01.

- [ ] **Step 5: Commit**

```bash
git add dbt/models/marts/dim_date.sql dbt/models/marts/_marts.yml
git commit -m "Add dim_date generated from 30-year spine"
```

---

## Task 3: Build `dim_product`

**Goal:** Passthrough dim from `stg_products` with one column rename to avoid a clash with the fact's `created_at`.

**Files:**
- Create: `dbt/models/marts/dim_product.sql`
- Modify: `dbt/models/marts/_marts.yml` — add tests for `dim_product`

- [ ] **Step 1: Write the model SQL**

Write to `dbt/models/marts/dim_product.sql`:

```sql
{{ config(materialized='table') }}

select
    product_id,
    product_name,
    product_description,
    created_at as product_created_at
from {{ ref('stg_products') }}
```

- [ ] **Step 2: Add schema tests to `_marts.yml`**

Add to the `models:` list in `dbt/models/marts/_marts.yml`:

```yaml
  - name: dim_product
    description: Product dimension. SCD Type 1 — current attributes only, no history.
    columns:
      - name: product_id
        description: Primary key.
        data_tests:
          - unique
          - not_null
      - name: product_name
        data_tests:
          - not_null
      - name: product_description
      - name: product_created_at
        description: Renamed from stg_products.created_at to avoid clashing with the fact's created_at.
```

- [ ] **Step 3: Build the model and run its tests**

Run (with pre-flight prefix):
```bash
cd dbt && dbt build --select dim_product
```
Expected: all PASS, no errors.

- [ ] **Step 4: Verify row count matches source**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM RAW.products')
src = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM ANALYTICS.dim_product')
dim = cur.fetchone()[0]
print(f'RAW.products: {src} rows, ANALYTICS.dim_product: {dim} rows, match: {src == dim}')
cur.close(); conn.close()
"
```
Expected: `match: True`.

- [ ] **Step 5: Commit**

```bash
git add dbt/models/marts/dim_product.sql dbt/models/marts/_marts.yml
git commit -m "Add dim_product passthrough from stg_products"
```

---

## Task 4: Build `int_order_items_with_refunds`

**Goal:** Intermediate view that joins `stg_order_items` to a per-item refund total. Isolates the LEFT JOIN + SUM logic so it can be tested independently of the fact.

**Files:**
- Create: `dbt/models/intermediate/int_order_items_with_refunds.sql`
- Create: `dbt/models/intermediate/_intermediate.yml`

- [ ] **Step 1: Write the model SQL**

Write to `dbt/models/intermediate/int_order_items_with_refunds.sql`:

```sql
{{ config(materialized='view') }}

with refunds_per_item as (
    select
        order_item_id,
        sum(refund_amount_usd) as refund_amount_usd
    from {{ ref('stg_order_item_refunds') }}
    group by order_item_id
)

select
    oi.order_item_id,
    oi.order_id,
    oi.product_id,
    oi.is_primary_item,
    oi.price_usd,
    oi.cogs_usd,
    coalesce(r.refund_amount_usd, 0)::numeric(12, 2) as refund_amount_usd,
    oi.created_at
from {{ ref('stg_order_items') }} oi
left join refunds_per_item r
    on oi.order_item_id = r.order_item_id
```

- [ ] **Step 2: Write schema tests to `_intermediate.yml`**

Write to `dbt/models/intermediate/_intermediate.yml`:

```yaml
version: 2

models:
  - name: int_order_items_with_refunds
    description: >
      stg_order_items LEFT JOINed to summed refunds per line item.
      Same row count as stg_order_items.
    columns:
      - name: order_item_id
        description: Primary key.
        data_tests:
          - unique
          - not_null
      - name: order_id
        data_tests:
          - not_null
      - name: product_id
        data_tests:
          - not_null
      - name: price_usd
        data_tests:
          - not_null
      - name: refund_amount_usd
        description: Sum of refunds for this line item, COALESCEd to 0.
        data_tests:
          - not_null
```

- [ ] **Step 3: Build the model and run its tests**

Run (with pre-flight prefix):
```bash
cd dbt && dbt build --select int_order_items_with_refunds
```
Expected: PASS for the view build and all tests.

- [ ] **Step 4: Verify row count matches `stg_order_items`**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM ANALYTICS.stg_order_items')
stg = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM ANALYTICS.int_order_items_with_refunds')
intm = cur.fetchone()[0]
print(f'stg_order_items: {stg}, int_order_items_with_refunds: {intm}, match: {stg == intm}')
cur.close(); conn.close()
"
```
Expected: `match: True`.

- [ ] **Step 5: Spot-check that refund totals look right**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
cur.execute('''SELECT
    COUNT(*) AS total_lines,
    COUNT_IF(refund_amount_usd > 0) AS lines_with_refund,
    SUM(refund_amount_usd) AS total_refunded
FROM ANALYTICS.int_order_items_with_refunds''')
print(cur.fetchone())
cur.close(); conn.close()
"
```
Expected: a row showing total_lines == stg_order_items count, plus some non-zero `lines_with_refund` and `total_refunded`.

- [ ] **Step 6: Commit**

```bash
git add dbt/models/intermediate/
git commit -m "Add int_order_items_with_refunds view for line-item refund totals"
```

---

## Task 5: Build `fct_order_items`

**Goal:** The fact table — joins the intermediate to `stg_orders` for `primary_product_id` and `user_id`, computes derived measures, materializes as a table.

**Files:**
- Create: `dbt/models/marts/fct_order_items.sql`
- Modify: `dbt/models/marts/_marts.yml` — add tests for `fct_order_items` including `relationships` to `dim_product` and `dim_date`

- [ ] **Step 1: Write the model SQL**

Write to `dbt/models/marts/fct_order_items.sql`:

```sql
{{ config(materialized='table') }}

with order_context as (
    select
        order_id,
        primary_product_id,
        user_id
    from {{ ref('stg_orders') }}
)

select
    -- Degenerate dimensions
    oi.order_item_id,
    oi.order_id,
    o.user_id,

    -- Foreign keys to dimensions
    oi.created_at::date as date_key,
    oi.product_id,
    o.primary_product_id,

    -- Atomic measures
    oi.price_usd,
    oi.cogs_usd,
    oi.refund_amount_usd,
    oi.is_primary_item,

    -- Derived measures
    (oi.price_usd - oi.cogs_usd)::numeric(12, 2) as gross_profit_usd,
    (oi.price_usd - oi.refund_amount_usd)::numeric(12, 2) as net_revenue_usd,
    (oi.price_usd - oi.cogs_usd - oi.refund_amount_usd)::numeric(12, 2) as net_profit_usd,
    oi.refund_amount_usd > 0 as has_refund,

    -- Timestamp
    oi.created_at
from {{ ref('int_order_items_with_refunds') }} oi
inner join order_context o on oi.order_id = o.order_id
```

- [ ] **Step 2: Add schema tests to `_marts.yml`**

Add to the `models:` list in `dbt/models/marts/_marts.yml`:

```yaml
  - name: fct_order_items
    description: >
      Fact at order line-item grain. One row per order_item_id. Joins
      int_order_items_with_refunds to stg_orders for primary_product_id and user_id.
    columns:
      - name: order_item_id
        description: Primary key (degenerate dimension).
        data_tests:
          - unique
          - not_null
      - name: order_id
        description: Degenerate dimension. Group by this to see basket contents.
        data_tests:
          - not_null
      - name: user_id
        description: Degenerate dimension. Use COUNT DISTINCT for customer counts.
      - name: date_key
        description: FK to dim_date.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_date')
                field: date_key
      - name: product_id
        description: FK to dim_product (line item's product).
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_product')
                field: product_id
      - name: primary_product_id
        description: FK to dim_product (order's headline product, role-playing dim).
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_product')
                field: product_id
      - name: price_usd
        data_tests:
          - not_null
      - name: cogs_usd
        data_tests:
          - not_null
      - name: refund_amount_usd
        data_tests:
          - not_null
      - name: is_primary_item
        data_tests:
          - not_null
      - name: gross_profit_usd
        description: price_usd - cogs_usd.
      - name: net_revenue_usd
        description: price_usd - refund_amount_usd.
      - name: net_profit_usd
        description: price_usd - cogs_usd - refund_amount_usd.
      - name: has_refund
        description: True when refund_amount_usd > 0.
        data_tests:
          - accepted_values:
              arguments:
                values: [true, false]
```

- [ ] **Step 3: Build the model and run its tests**

Run (with pre-flight prefix):
```bash
cd dbt && dbt build --select fct_order_items
```
Expected: PASS for the table build, all not_null tests, and all 3 `relationships` tests.

- [ ] **Step 4: Spot-check the derived measures**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
cur.execute('''SELECT
    SUM(price_usd) AS total_revenue,
    SUM(gross_profit_usd) AS total_gross_profit,
    SUM(net_revenue_usd) AS total_net_revenue,
    SUM(refund_amount_usd) AS total_refunds
FROM ANALYTICS.fct_order_items''')
row = cur.fetchone()
total_rev, gp, nr, refunds = row
print(f'revenue={total_rev} gross_profit={gp} net_revenue={nr} refunds={refunds}')
print(f'sanity check: net_revenue + refunds == revenue? {abs((nr or 0) + (refunds or 0) - (total_rev or 0)) < 0.01}')
cur.close(); conn.close()
"
```
Expected: `sanity check: ... True`. The derived measures are mutually consistent.

- [ ] **Step 5: Commit**

```bash
git add dbt/models/marts/fct_order_items.sql dbt/models/marts/_marts.yml
git commit -m "Add fct_order_items fact table at order line-item grain"
```

---

## Task 6: Add singular tests

**Goal:** Four custom SQL tests in `dbt/tests/` that catch business-logic violations not covered by schema tests.

**Files:**
- Create: `dbt/tests/assert_refund_not_exceeds_price.sql`
- Create: `dbt/tests/assert_refund_amount_not_negative.sql`
- Create: `dbt/tests/assert_one_primary_item_per_order.sql`
- Create: `dbt/tests/assert_fct_rowcount_matches_stg.sql`

- [ ] **Step 1: Write `assert_refund_not_exceeds_price.sql`**

Write to `dbt/tests/assert_refund_not_exceeds_price.sql`:

```sql
-- Returns rows where refund exceeds the original price.
-- Should always be empty: you can't refund more than you charged.
select
    order_item_id,
    price_usd,
    refund_amount_usd
from {{ ref('fct_order_items') }}
where refund_amount_usd > price_usd
```

- [ ] **Step 2: Write `assert_refund_amount_not_negative.sql`**

Write to `dbt/tests/assert_refund_amount_not_negative.sql`:

```sql
-- Returns rows where refund_amount_usd is negative.
-- Should always be empty.
select
    order_item_id,
    refund_amount_usd
from {{ ref('fct_order_items') }}
where refund_amount_usd < 0
```

- [ ] **Step 3: Write `assert_one_primary_item_per_order.sql`**

Write to `dbt/tests/assert_one_primary_item_per_order.sql`:

```sql
-- Each order should have exactly one row with is_primary_item = true.
-- Returns rows where the count is anything other than 1.
select
    order_id,
    count(*) as primary_item_count
from {{ ref('fct_order_items') }}
where is_primary_item = true
group by order_id
having count(*) <> 1
```

- [ ] **Step 4: Write `assert_fct_rowcount_matches_stg.sql`**

Write to `dbt/tests/assert_fct_rowcount_matches_stg.sql`:

```sql
-- The fact's INNER JOIN to stg_orders could silently drop rows if any line item
-- references a missing order. Cross-join the row counts; this returns rows
-- only when fct and stg disagree.
with fct_count as (
    select count(*) as n from {{ ref('fct_order_items') }}
),
stg_count as (
    select count(*) as n from {{ ref('stg_order_items') }}
)
select
    fct_count.n as fct_n,
    stg_count.n as stg_n
from fct_count
cross join stg_count
where fct_count.n <> stg_count.n
```

- [ ] **Step 5: Run all singular tests**

Run (with pre-flight prefix):
```bash
cd dbt && dbt test --select test_type:singular
```
Expected: 4 tests, all PASS. If `assert_one_primary_item_per_order` fails, the source data has orders with zero or multiple primary items — surface this to the team rather than relaxing the test.

- [ ] **Step 6: Commit**

```bash
git add dbt/tests/
git commit -m "Add singular tests for fct_order_items invariants"
```

---

## Task 7: Full integration build

**Goal:** Build the entire DAG end-to-end (sources → staging → intermediate → marts) with all tests, to confirm nothing was missed.

**Files:** none (verification only).

- [ ] **Step 1: Run full `dbt build`**

Run (with pre-flight prefix):
```bash
cd dbt && dbt build
```
Expected: every model builds, every test passes, `Done. PASS=<N> WARN=0 ERROR=0 SKIP=0` at the bottom. The total includes everything from staging onward.

- [ ] **Step 2: Run a Maya-style sample query against the new fact**

Run (with pre-flight prefix):
```bash
python -c "
from pipeline.config import get_snowflake_connection
conn = get_snowflake_connection()
cur = conn.cursor()
# Theme A: top products by net revenue last 90 days
cur.execute('''
SELECT
    p.product_name,
    SUM(f.net_revenue_usd) AS net_revenue,
    COUNT(DISTINCT f.order_id) AS orders,
    COUNT(*) AS units
FROM ANALYTICS.fct_order_items f
JOIN ANALYTICS.dim_product p USING (product_id)
WHERE f.date_key >= DATEADD(day, -90, CURRENT_DATE())
GROUP BY p.product_name
ORDER BY net_revenue DESC
LIMIT 5
''')
for row in cur.fetchall():
    print(row)
cur.close(); conn.close()
"
```
Expected: up to 5 rows, one per product, ranked by 90-day net revenue. If 0 rows, the date range may be older than current date — adjust window or check data freshness.

- [ ] **Step 3: No commit** — this task is verification only, no files changed.

---

## Task 8: Deprecate `monthly_sales_summary`

**Goal:** Add a deprecation header to the existing legacy mart. Keep it queryable for now — Maya will validate her existing dashboards against `fct_order_items` aggregated up to month/product before we delete the file in a follow-up PR.

**Files:**
- Modify: `dbt/models/marts/monthly_sales_summary.sql` — add a comment block at the top.

- [ ] **Step 1: Read the current file**

```bash
cat /Users/greglontok/isba-4715/basket-craft-pipeline/dbt/models/marts/monthly_sales_summary.sql
```

- [ ] **Step 2: Prepend a deprecation comment**

Add this comment block as the first lines of `dbt/models/marts/monthly_sales_summary.sql` (preserving the existing SQL below it):

```sql
-- DEPRECATED 2026-04-26: superseded by fct_order_items + dim_product + dim_date.
-- Maya is validating existing dashboards against the new star schema.
-- Once she confirms numbers match, this file will be removed in a follow-up PR.
-- New equivalent query:
--   SELECT
--       date_trunc('month', f.date_key)::date AS month,
--       p.product_name,
--       SUM(f.price_usd) AS total_revenue,
--       COUNT(DISTINCT f.order_id) AS order_count
--   FROM ANALYTICS.fct_order_items f
--   JOIN ANALYTICS.dim_product p USING (product_id)
--   GROUP BY 1, 2
--   ORDER BY 1, 2;
```

- [ ] **Step 3: Verify dbt still parses**

Run (with pre-flight prefix):
```bash
cd dbt && dbt parse
```
Expected: no errors. SQL comments don't affect parse.

- [ ] **Step 4: Commit**

```bash
git add dbt/models/marts/monthly_sales_summary.sql
git commit -m "Mark monthly_sales_summary deprecated; superseded by fct_order_items"
```

---

## Self-Review Checklist (run before declaring plan complete)

- **Spec coverage:**
  - Stakeholder, Themes A+B+D — implicit in the goal/architecture sections.
  - Architecture (5-layer) — Tasks 2–5 build all four new models.
  - Materialization (views for staging/intermediate, tables for marts) — encoded in `{{ config(materialized=...) }}` blocks per model.
  - Grain (line-item) — `fct_order_items` task; `assert_fct_rowcount_matches_stg` enforces no row drops.
  - Components (4 models) — Task 2 (`dim_date`), Task 3 (`dim_product`), Task 4 (`int_order_items_with_refunds`), Task 5 (`fct_order_items`). ✓
  - Schema tests — Tasks 2, 3, 4, 5 each include `_marts.yml` / `_intermediate.yml` updates. ✓
  - Singular tests (4) — Task 6 covers all four. ✓
  - Build order (auto from `ref()`) — Task 7 runs full `dbt build`. ✓
  - Failure behavior — covered by default `severity: error`; documented in spec.
  - Migration plan for `monthly_sales_summary` — Task 8 marks it deprecated. ✓
  - Out of scope — none of the deferred items appear in any task. ✓

- **Placeholder scan:** no "TBD"/"TODO"/"similar to Task N" — every step has actual code. ✓

- **Type/name consistency:** `date_key` is `DATE` everywhere. `refund_amount_usd` is `NUMERIC(12,2)` everywhere. `is_primary_item` is `BOOLEAN` (cast in staging, preserved through intermediate and fact). Model names match across YAML and SQL. ✓
