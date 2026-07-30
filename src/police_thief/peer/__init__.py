"""One peer: server, client, state machine, orchestrator.

Each peer is a self-contained process. Two of them play a match by talking
directly to each other; there is no third process, no shared file and no shared
memory. Ch. 2 (PDF pp. 25-26): "each agent is simultaneously a server exposing
tools and a client calling the opponent's tools. There is no 'strong' side and
'weak' side; the two peers are completely equivalent in their network role."
"""
