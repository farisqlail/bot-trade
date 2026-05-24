# Database ERD

```
┌─────────────────────────────────┐
│              users              │
├──────────────┬──────────────────┤
│ id           │ PK INT           │
│ email        │ VARCHAR(255) UQ  │
│ username     │ VARCHAR(100) UQ  │
│ hashed_pass  │ VARCHAR(255)     │
│ is_active    │ BOOL             │
│ is_superuser │ BOOL             │
│ failed_login │ INT              │
│ locked_until │ TIMESTAMPTZ      │
│ last_login   │ TIMESTAMPTZ      │
│ created_at   │ TIMESTAMPTZ      │
│ updated_at   │ TIMESTAMPTZ      │
└──────┬───────┴──────────────────┘
       │ 1
       │
       ├─────────────── 1 ──────────────────┐
       │                                    │
       │ n                                  │ 1
┌──────▼───────────────────────────┐  ┌────▼─────────────────────────┐
│              trades              │  │           settings            │
├──────────────┬───────────────────┤  ├──────────────┬───────────────┤
│ id           │ PK INT            │  │ id           │ PK INT        │
│ user_id      │ FK → users.id     │  │ user_id      │ FK → users.id │
│ exchange_oid │ VARCHAR(100)      │  │ symbol       │ VARCHAR(20)   │
│ symbol       │ VARCHAR(20)       │  │ leverage     │ INT           │
│ direction    │ ENUM(LONG,SHORT)  │  │ risk_percent │ FLOAT         │
│ status       │ ENUM(*)           │  │ max_trades   │ INT           │
│ entry_price  │ FLOAT             │  │ default_sl   │ FLOAT         │
│ stop_loss    │ FLOAT             │  │ default_tp   │ FLOAT         │
│ take_profit  │ FLOAT             │  │ daily_limit  │ FLOAT         │
│ exit_price   │ FLOAT             │  │ max_dd       │ FLOAT         │
│ quantity     │ FLOAT             │  │ consec_limit │ INT           │
│ leverage     │ INT               │  │ bot_enabled  │ BOOL          │
│ risk_amount  │ FLOAT             │  │ auto_trade   │ BOOL          │
│ risk_percent │ FLOAT             │  │ ai_enabled   │ BOOL          │
│ pnl          │ FLOAT             │  │ api_key      │ VARCHAR(255)  │
│ pnl_percent  │ FLOAT             │  │ api_secret   │ VARCHAR(255)  │
│ fees         │ FLOAT             │  │ use_testnet  │ BOOL          │
│ signal_id    │ FK → signals.id   │  │ notif_set    │ JSON          │
│ notes        │ TEXT              │  │ created_at   │ TIMESTAMPTZ   │
│ opened_at    │ TIMESTAMPTZ       │  │ updated_at   │ TIMESTAMPTZ   │
│ closed_at    │ TIMESTAMPTZ       │  └──────────────┴───────────────┘
│ created_at   │ TIMESTAMPTZ       │
│ updated_at   │ TIMESTAMPTZ       │        ┌─────────────────────────────────┐
└──────────────┴────────┬──────────┘        │           risk_events           │
                        │ n                 ├──────────────┬──────────────────┤
                        │                   │ id           │ PK INT           │
┌───────────────────────▼──────────┐        │ user_id      │ FK → users.id    │
│             signals              │        │ event_type   │ ENUM(*)          │
├──────────────┬───────────────────┤        │ severity     │ ENUM(*)          │
│ id           │ PK INT            │        │ title        │ VARCHAR(200)     │
│ symbol       │ VARCHAR(20) IDX   │        │ description  │ TEXT             │
│ signal_type  │ ENUM(BUY/SELL/HLD)│        │ triggered_v  │ FLOAT            │
│ source       │ ENUM(*)           │        │ threshold_v  │ FLOAT            │
│ price_at_sig │ FLOAT             │        │ action_taken │ VARCHAR(200)     │
│ suggested_e  │ FLOAT             │        │ metadata     │ JSON             │
│ suggested_sl │ FLOAT             │        │ is_resolved  │ INT              │
│ suggested_tp │ FLOAT             │        │ resolved_at  │ TIMESTAMPTZ      │
│ confidence   │ FLOAT             │        │ created_at   │ TIMESTAMPTZ      │
│ reasoning    │ TEXT              │        └──────────────┴──────────────────┘
│ indicators   │ TEXT              │
│ is_executed  │ BOOL              │        ┌─────────────────────────────────┐
│ created_at   │ TIMESTAMPTZ       │        │          ai_analysis            │
│ expires_at   │ TIMESTAMPTZ       │        ├──────────────┬──────────────────┤
└──────────────┴───────────────────┘        │ id           │ PK INT           │
                                            │ symbol       │ VARCHAR(20) IDX  │
                                            │ model_name   │ VARCHAR(100)     │
                                            │ trend        │ VARCHAR(20)      │
                                            │ sentiment    │ VARCHAR(20)      │
                                            │ confidence   │ FLOAT            │
                                            │ support_lvls │ JSON             │
                                            │ resist_lvls  │ JSON             │
                                            │ key_levels   │ JSON             │
                                            │ analysis_txt │ TEXT             │
                                            │ raw_response │ TEXT             │
                                            │ mkt_snapshot │ JSON             │
                                            │ price_at     │ FLOAT            │
                                            │ rec_action   │ VARCHAR(20)      │
                                            │ sug_entry    │ FLOAT            │
                                            │ sug_sl       │ FLOAT            │
                                            │ sug_tp       │ FLOAT            │
                                            │ proc_time_ms │ INT              │
                                            │ created_at   │ TIMESTAMPTZ      │
                                            └──────────────┴──────────────────┘

Relationships:
  users 1──n trades
  users 1──1 settings
  users 1──n risk_events
  signals 1──n trades
  ai_analysis (standalone, no FK — market-wide data)

Indexes:
  users: email(UQ), username(UQ)
  trades: user_id, symbol, status
  signals: symbol
  ai_analysis: symbol
  risk_events: user_id
```
