# Known Issues & Technical Debt

## Resolved This Session (2026-04-23)
- ✓ Abdul Malik team messages now routed to handle_team_message()
- ✓ Phone normalization with normalize_phone() applied in poll handler
- ✓ ERPNext auth wired to /api/auth/login with real Bearer tokens
- ✓ Frontend login replaced with real auth flow
- ✓ Role-aware UI: Financial tools hidden from team role
- ✓ sessions table added to DB
- ✓ Rotating file logs: app.log, error.log, whatsapp.log

## Open Issues
- [ ] Mobile responsive layout needs QA on actual devices
- [ ] Google Meet scheduling: verify token refresh works long-term
- [ ] Pricing context fetched on every customer message — should cache (5 min TTL)
- [ ] Sessions stored in SQLite — fine for now, consider Redis if concurrent users grow
- [ ] HTTPS/SSL not configured for web dashboard (currently HTTP)
- [ ] WhatsApp media messages (images, docs) silently ignored
- [ ] Pakistan-number team members need verification in whitelist

## Technical Debt
- wa_message_name dedup fix needs monitoring in production
- handle_team_message() redirect message ("I can only help with tickets")
  could be improved to at least forward to Talha for unknowns
- config.py uses Python dict, not JSON — harder to edit without Python
- cloud_agent.py is ~5400 lines — consider splitting into modules
- .bak files (cloud_agent.py.bak, database.py.bak) should be cleaned up

## Deferred Features
- Mobile app (PWA or React Native)
- Role-based ticket assignment view (show only assigned tickets per team member)
- Multi-client Donna instances
- WhatsApp media handling (images, documents)
- Automated backup to cloud storage
