from pathlib import Path
import hashlib
import json
import subprocess
import chess
from PIL import Image, ImageDraw, ImageFont
import numpy as np

root=Path(__file__).resolve().parents[2]
out=root/'work/android-vision-tests';out.mkdir(exist_ok=True,parents=True)
config=json.loads((root/'config.json').read_text())
templates=root/config['templates_dir']
names={'P':'white_pawn','N':'white_knight','B':'white_bishop','R':'white_rook','Q':'white_queen','K':'white_king',
       'p':'black_pawn','n':'black_knight','b':'black_bishop','r':'black_rook','q':'black_queen','k':'black_king','.':'empty'}
tiles={symbol:list((templates/name).glob('*.png')) for symbol,name in names.items()}
def render(board,flipped=False,box=(40,260,680,900),screen=(720,1280),highlight=(),coordinates=False):
    image=Image.new('RGB',screen,(40,50,65))
    left,top,right,bottom=box
    for row in range(8):
        for col in range(8):
            square=(row*8+7-col) if flipped else ((7-row)*8+col)
            piece=board.piece_at(square);symbol=piece.symbol() if piece else '.'
            candidates=tiles[symbol]
            same=[p for p in candidates if (chess.square_rank(chess.parse_square(p.stem))+chess.square_file(chess.parse_square(p.stem)))%2==(chess.square_rank(square)+chess.square_file(square))%2]
            tile=Image.open((same or candidates)[0]).convert('RGB')
            if coordinates:
                colours,counts=np.unique(np.asarray(tile).reshape(-1,3),axis=0,return_counts=True)
                background=tuple(int(v) for v in colours[counts.argmax()])
                painter=ImageDraw.Draw(tile);tw,th=tile.size
                painter.rectangle((0,0,int(tw*.22),int(th*.26)),fill=background)
                painter.rectangle((int(tw*.78),int(th*.83),tw,th),fill=background)
            if square in highlight:
                # Change the board colour while preserving grayscale pieces and antialiasing.
                pixels=np.asarray(tile).astype(float)
                colours,counts=np.unique(pixels.reshape(-1,3),axis=0,return_counts=True)
                background=colours[counts.argmax()]
                tint=np.array((186,202,68) if (chess.square_rank(square)+chess.square_file(square))%2==0 else (246,246,105))
                chroma=background.max()-background.min()
                alpha=np.clip((pixels.max(axis=2)-pixels.min(axis=2))/max(1,chroma),0,1)
                pixels+=alpha[:,:,None]*(tint-background)
                tile=Image.fromarray(np.uint8(np.clip(pixels,0,255)))
            x=left+col*(right-left)//8;y=top+row*(bottom-top)//8
            w=left+(col+1)*(right-left)//8-x;h=top+(row+1)*(bottom-top)//8-y
            tile=tile.resize((w,h))
            if coordinates:
                painter=ImageDraw.Draw(tile);font=ImageFont.truetype('arial.ttf',max(10,int(h*.16)))
                ink=(235,237,207) if (chess.square_rank(square)+chess.square_file(square))%2==0 else (145,166,111)
                if col==0:painter.text((w*.04,h*.02),str(chess.square_rank(square)+1),fill=ink,font=font)
                if row==7:painter.text((w*.86,h*.81),chess.FILE_NAMES[chess.square_file(square)],fill=ink,font=font)
            image.paste(tile,(x,y))
    return image
board=chess.Board();render(board).save(out/'start.png')
cases=[]
for i,move in enumerate(['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6','e1g1','f8e7']):
    board.push_uci(move)
    for flipped in (False,True):
        name=f'{i}-{flipped}.png';frame=render(board,flipped)
        draw=ImageDraw.Draw(frame)
        for row,col in [(2,3),(4,4)]:
            x=40+(col+.87)*80;y=260+(row+.13)*80
            draw.ellipse((x-6,y-6,x+6,y+6),fill=(15,160,175))
        frame.save(out/name)
        cases.append(f'{name} {"black" if flipped else "white"} {board.board_fen()}')
(out/'cases.txt').write_text('\n'.join(cases))
Image.new('RGB',(720,1280),(80,80,80)).save(out/'blank.png')
# Full-width Android boards, odd tile dimensions, last-move highlight, and flipped view.
suites=[]
mobile_moves=['e2e4','e7e6','g1f3','d7d5','b1c3','g8f6','f1b5','c7c6','b5d3','f8b4']
for width,height,top in [(738,1600,464),(1080,2340,678),(720,1560,452)]:
    box=(0,top,width,top+width)
    for flipped in (False,True):
        prefix=f'mobile-{width}-{flipped}'
        initial=render(chess.Board(),flipped,box,(width,height))
        initial.save(out/f'{prefix}-start.png')
        position=chess.Board()
        mobile_cases=[]
        for i,uci in enumerate(mobile_moves):
            move=chess.Move.from_uci(uci);position.push(move)
            name=f'{prefix}-{i}.png'
            render(position,flipped,box,(width,height),(move.from_square,move.to_square)).save(out/name)
            mobile_cases.append(f'{name} {"black" if flipped else "white"} {position.board_fen()}')
            if width==738 and not flipped and i==1:
                obscured=render(position,flipped,box,(width,height),(move.from_square,move.to_square))
                draw=ImageDraw.Draw(obscured)
                for y in range(top+2*width//8,top+3*width//8):
                    for x in range(4*width//8,5*width//8):
                        draw.point((x,y),fill=(255,0,255) if (x//5+y//7)%2 else (0,0,0))
                obscured.save(out/'obscured-e6.png')
        (out/f'{prefix}.txt').write_text('\n'.join(mobile_cases))
        suites.append(f'{prefix} {"black" if flipped else "white"} '+','.join(map(str,box)))
(out/'suites.txt').write_text('\n'.join(suites))
coordinate_cases=0
for flipped in (False,True):
    prefix=f'coords-{flipped}';position=chess.Board();box=(0,464,738,1202)
    render(position,flipped,box,(738,1600),coordinates=True).save(out/f'{prefix}-start.png')
    sequence=[]
    # Reconstruct the user's position after 1.d4 d6 2.e4 Nf6 3.Nc3 e5.
    for i,uci in enumerate(['d2d4','d7d6','e2e4','g8f6','b1c3','e7e5']):
        move=chess.Move.from_uci(uci);position.push(move);name=f'{prefix}-{i}.png'
        render(position,flipped,box,(738,1600),(move.from_square,move.to_square),True).save(out/name)
        sequence.append(f'{name} {"black" if flipped else "white"} {position.board_fen()}')
    (out/f'{prefix}.txt').write_text('\n'.join(sequence));coordinate_cases+=len(sequence)
sources=list((root/'android/tests/stubs').rglob('*.java'))+[root/'android/tests/VisionCheck.java']+[root/f'android/app/src/main/java/id/chesslab/coach/{name}.java' for name in ['Vision','Board']]
subprocess.run(['javac','-encoding','UTF-8','-d',str(out)]+[str(p) for p in sources],check=True)
subprocess.run(['java','-cp',str(out),'VisionCheck',str(out)],check=True)
report=json.loads((out/'checks.json').read_text())
report.update({
    'fixture_positions':len(cases)+len(suites)*len(mobile_moves)+coordinate_cases,
    'mobile_widths':[738,1080,720],
    'mobile_autodetection_checks':len(suites)*2,
    'midgame_training_rejections':len(suites),
    'blank_capture_rejected':True,
    'per_square_diagnostic_tested':True,
    'theme_save_load_tested':True,
    'runtime':'JVM image adapter; not an Android device',
    'source_sha256':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sources+[Path(__file__).resolve()]},
})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
