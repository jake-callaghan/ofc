import test from 'node:test';
import assert from 'node:assert/strict';
import { invitation, invitationLink, route } from '../src/lib/navigation.js';

const game = 'f0fd6020-253d-4dc6-9cce-5f68e21c55b6';
const invite = 'abcdefghijklmnopqrstuvwxyz012345';

test('compact invitations round-trip without changing the secret', () => {
  const link = invitationLink(
    'https://ofcpoker.live/?unused=1#game=old',
    game,
    invite,
  );
  assert.equal(
    link,
    'https://ofcpoker.live/#join/8P1gICU9Tcaczl9o4hxVtg/' + invite,
  );
  assert.deepEqual(invitation(link), { game, invite });
});

test('existing invitations still work', () => {
  const link =
    'https://ofcpoker.live/#join=' +
    encodeURIComponent(JSON.stringify({ game, invite }));
  assert.deepEqual(invitation(link), { game, invite });
});

test('invalid invitations have a useful error', () => {
  for (const value of [
    'hello',
    'https://ofcpoker.live/',
    'https://ofcpoker.live/#join/nope/secret',
  ]) {
    assert.throws(() => invitation(value), /complete invitation link/);
  }
});

test('compact routes open the join screen', () => {
  const previous = globalThis.location;
  try {
    globalThis.location = new URL(
      invitationLink('https://ofcpoker.live/', game, invite),
    );
    assert.equal(route().join, globalThis.location.href);
    assert.equal(route().id, null);
  } finally {
    if (previous === undefined) delete globalThis.location;
    else globalThis.location = previous;
  }
});
