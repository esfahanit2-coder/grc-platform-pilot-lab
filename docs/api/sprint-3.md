# Sprint 3 API — Controls, Assets, Risk and RTP

All endpoints are under `/api/v1/` and require JWT plus `X-Tenant-ID`.

## Common controls

- `GET/POST /controls/`
- `GET/PATCH/DELETE /controls/{id}/`
- `POST /controls/{id}/duplicate/`
- `GET/POST /control-requirements/`
- `GET/POST /control-implementations/`

Global controls are visible but read-only. Tenant users may implement an active global control in their own organization scope.

## Assets

- `GET/POST /assets/`
- `GET/PATCH/DELETE /assets/{id}/`
- `GET/POST /asset-dependencies/`

Asset access is restricted to the organization scopes granted to the current user.

## Risk

- `GET/POST /risks/`
- `GET/PATCH/DELETE /risks/{id}/`
- `POST /risks/{id}/evaluate/`
- `GET /risks/{id}/rtp/`
- `GET /risks/{id}/rtp/?format=docx`
- `GET/POST /risk-methodologies/`
- `GET/POST /risk-controls/`
- `GET/POST /risk-treatments/`
- `POST /risk-treatments/{id}/accept/`
- `POST /risk-treatments/{id}/actions/`

### Evaluate risk

```json
{
  "methodology": "<uuid>",
  "evaluation_type": "inherent",
  "likelihood": 5,
  "impact": 4,
  "rationale": "Internet-facing privileged service"
}
```

Sprint 3 implements the `product` formula in runtime (`Likelihood × Impact`). Methodology scales and thresholds remain data-driven, allowing additional formulas in later versions without altering the Risk entity.

## Actions

- `GET/POST /actions/`
- `PATCH /actions/{id}/`

Sprint 3 introduces the generic Action foundation because RTP needs executable treatment actions. Sprint 4 will extend it for findings, assessments and audit remediation.

## Permission codes

- `control.view`
- `control.manage`
- `control.implementation.view`
- `control.implementation.manage`
- `asset.view`
- `asset.manage`
- `risk.view`
- `risk.manage`
- `risk.evaluate`
- `risk.treatment.manage`
- `action.view`
- `action.manage`
