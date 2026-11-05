# systemd unit (example)

`qwen-flashnext-strata.service` is the user unit from my rig, paths as they are there. It reads the card set from an env
file that my dashboard writes before start (`GPUS=2,3`), waits until those cards are free, starts `serve.server` on port
18000 without an API key, saves the live conversation on stop and restores it after start (the session patch). The
`Conflicts=` line lists the other model servers on the same port, so starting one stops the others.
