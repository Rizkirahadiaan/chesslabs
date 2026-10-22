from pathlib import Path
import random
import subprocess
import chess

root=Path(__file__).resolve().parents[2]
out=root/'work/android-rule-tests'
out.mkdir(parents=True,exist_ok=True)
subprocess.run(['javac','-encoding','UTF-8','-d',str(out),str(root/'android/app/src/main/java/id/chesslab/coach/Board.java'),str(root/'android/tests/BoardCheck.java')],check=True)
subprocess.run(['java','-cp',str(out),'BoardCheck','perft'],check=True)
boards=[chess.Board(),chess.Board('r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'),
        chess.Board('8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1'),
        chess.Board('4k3/P7/8/8/8/8/7p/4K3 w - - 0 1')]
rng=random.Random(143)
for _ in range(8):
    board=chess.Board()
    for ply in range(90):
        if board.is_game_over():break
        board.push(rng.choice(list(board.legal_moves)))
        if ply%3==0:boards.append(board.copy())
proc=subprocess.run(['java','-cp',str(out),'BoardCheck'],input='\n'.join(b.fen() for b in boards)+'\n',text=True,capture_output=True,check=True)
lines=proc.stdout.splitlines()
assert len(lines)==len(boards)
for board,line in zip(boards,lines):
    expected={m.uci() for m in board.legal_moves};actual=set(line.split())
    assert actual==expected,(board.fen(),expected-actual,actual-expected)
print(f'{len(boards)} positions match python-chess legal moves')
