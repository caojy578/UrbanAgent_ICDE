# CARLA emergency-response prototype

This is the simulated urban emergency case in the paper. It is separate from the UrbanEval benchmark and does not produce the Table II–IV numbers.

An operator introduces a fire incident. The agent selects a response using the incident location, resource records, and route estimates, then deploys a UAV and a ground vehicle. Command acceptance and completion feedback come back through the bridge. A web dashboard shows the response.

Three programs, in call order:

| Directory | Role | Upstream |
| --- | --- | --- |
| `carla_bridge/` | Middleware between CARLA and agents. Socket.IO protocol v1, default `http://localhost:5000`, namespace `/agent`. | https://github.com/zxyangyu/CarlaBridge |
| `urban_agent/` | Hierarchical controller. Reads bridge snapshots, plans the response, and sends actor commands. Does not open a CARLA socket itself. | `urbanagent-main` in https://github.com/caojy578/UrbanAgent |
| `urban_frontend/` | Web dashboard for the operational picture. | https://github.com/ChaoqianO/urban_frontend |

Start the bridge first, then the controller, then the dashboard. Each directory has its own README and dependency file. Copy `.env.example` where a directory provides one, and do not commit filled-in secrets.

Protocol notes for the controller live in `urban_agent/README.md` (Bridge × Agent Protocol v1). Bridge design notes live in `carla_bridge/README.md` and `carla_bridge/bridge-agent-protocol-v1.md`.
