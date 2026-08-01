from UI.orb import FloatingOrb, OrbState

def test_orb_state_settable():
    orb = FloatingOrb(); orb.set_state(OrbState.LISTENING)
    assert orb.state == OrbState.LISTENING
