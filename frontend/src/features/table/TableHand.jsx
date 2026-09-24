import EmptyTable from './EmptyTable.jsx';
import Opponents from './Opponents.jsx';
import TurnEditor from './TurnEditor.jsx';
import HandResults from './HandResults.jsx';

export default function TableHand({
  game,
  session,
  busy,
  connection,
  command,
}) {
  const hand = game.hand;

  if (!hand) {
    return (
      <EmptyTable
        watching={!game.members.includes(session.player_id)}
        visibility={game.visibility}
      />
    );
  }

  const isPlaying = hand.players.includes(session.player_id);
  const isComplete = hand.status === 'complete';
  const draw = hand.draws[session.player_id] || [];
  const editorKey = `${hand.number}:${draw.join(',')}`;

  return (
    <>
      {isComplete && <HandResults game={game} />}

      <div className="hand-boards">
        {isPlaying && (
          <TurnEditor
            key={editorKey}
            game={game}
            session={session}
            busy={busy}
            connected={connection === 'live'}
            command={command}
          />
        )}

        {!isPlaying && (
          <div className="panel">
            <h2>
              {game.members.includes(session.player_id)
                ? 'Sitting out'
                : 'Watching'}
            </h2>
            <p>
              {game.members.includes(session.player_id)
                ? 'You can join the next hand.'
                : game.visibility === 'open'
                  ? 'Join the table to play in a future hand.'
                  : 'An invitation is required to join this private table.'}
            </p>
          </div>
        )}

        <Opponents
          hand={hand}
          names={game.player_names}
          playerId={session.player_id}
          nextFantasy={game.fantasy}
        />
      </div>
    </>
  );
}
