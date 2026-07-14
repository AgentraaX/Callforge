# API Contract

Owner: Person 4. Update this file in the same PR as any endpoint change — frontend
and the agent both rely on this being current, not the code being "self-documenting."

## Auth
### POST /auth/login
_Request/response shape TBD — Day 3._

## Campaigns
### GET /campaigns
### POST /campaigns
### GET /campaigns/{id}
### PATCH /campaigns/{id}
### POST /campaigns/{id}/leads

## Calls
### GET /calls
### GET /calls/{id}
### GET /calls/{id}/transcript
### POST /calls/{id}/takeover
### WS /calls/{id}/stream

## Objections
### GET /objections
### POST /objections
### PATCH /objections/{id}

## Analytics
### GET /analytics/conversion
### GET /analytics/objections
### GET /briefing/today
