# Two-minute demo script

Replay baseline (`make demo MODE=replay SCENARIO=demo_2min`) follows the
frozen `demo_2min` fixture timeline (idle → far entry → approach → occupancy
change → ambiguous interference → recovery):

| Time | Scene | What the UI shows |
| --- | --- | --- |
| 0:00–0:20 | idle | three signals quiet, sculpture slowly breathing, watermark visible |
| 0:20–0:40 | far entry | motion rises, depth proxy moves to far, council proposes claims |
| 0:40–1:05 | approach | motion high, depth mid, occupancy proxy rises; specialists appear in parallel |
| 1:05–1:30 | occupancy change | person still → occupancy high, motion low; RedTeam raises the interference confound; a claim is revised/conceded |
| 1:30–1:45 | ambiguous interference | PolicyArbiter rejects the demo overreach (metric-depth claim); Fusion result carries limits |
| 1:45–2:00 | recovery | signals return to idle; switch to Replay controls, seek to a marker, confirm reproducibility |

Audience-visible guarantees: current mode, data freshness, three signals,
measurement quality / model support / interpretation agreement shown
separately, limitations, and the `INFERENCE FIELD — NOT A CAMERA IMAGE`
watermark on every page. The Council page shows evidence chips and real
disagreement — never hidden chain-of-thought.
