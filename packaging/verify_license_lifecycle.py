"""Uji Coach Tk nyata terhadap stack lisensi lokal; hanya membuat data QA baru."""
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

import chess
import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    api_url=os.environ.get("CHESSLAB_QA_API","http://localhost:8080")
    email=os.environ["CHESSLAB_QA_ADMIN_EMAIL"]
    password=os.environ["CHESSLAB_QA_ADMIN_PASSWORD"]
    work=ROOT/"work"/("tk-license-"+uuid4().hex);work.mkdir()
    # Semua data cache dan konfigurasi uji tetap di folder khusus workspace.
    os.environ["LOCALAPPDATA"]=str(work/"appdata")
    os.environ["CHESSLAB_LICENSE_CONFIG"]=os.environ["CHESSLAB_QA_PUBLIC_CONFIG"]
    raw=json.loads((ROOT/"config.json").read_text())
    for name in ("stockfish_path","templates_dir","runtime_dir"):
        raw[name]=str((ROOT/raw.get(name,"runtime")).resolve())
    raw["auto_start"]=False
    training=os.environ.get("CHESSLAB_QA_TRAINING_BOARD")=="true"
    if training:
        raw.update(templates_dir=str(ROOT/"work/coach-vision-fixture"),player_colour="white",orientation_mode="white")
    config=work/"config.json";config.write_text(json.dumps(raw))
    with httpx.Client(base_url=api_url,timeout=10,trust_env=False) as client:
        client.headers["Origin"]=api_url
        response=client.post("/api/v1/admin/auth/login",json={"email":email,"password":password});response.raise_for_status()
        client.headers["X-CSRF-Token"]=client.cookies["chesslab_csrf"]
        customer=client.post("/api/v1/admin/customers",json={"name":"QA Desktop Tk","email":"qa-tk-"+uuid4().hex+"@example.com"});customer.raise_for_status()
        plans=client.get("/api/v1/admin/plans").json()["items"]
        plan=next(p for p in plans if p["name"]=="ChessLab Pro")
        issued=client.post("/api/v1/admin/licenses",json={"customer_id":customer.json()["id"],"product_id":plan["product_id"],"plan_id":plan["id"]});issued.raise_for_status()
        license_id=issued.json()["license"]["id"]
        from chesslab.coach import Coach
        app=Coach(config)
        app.root.withdraw()
        assert app.license_manager is not None
        app.license_panel.open_activation=lambda:None
        if training:
            import ctypes
            import tkinter as tk
            from PIL import Image, ImageTk
            from chesslab.board import PIECE_NAME_TO_SYMBOL
            from chesslab.coach import AFTER_E4_E5
            position=chess.Board(AFTER_E4_E5)
            names={value:name for name,value in PIECE_NAME_TO_SYMBOL.items()}
            picture=Image.new("RGB",(784,784))
            for square in chess.SQUARES:
                piece=position.piece_at(square)
                folder=names[piece.symbol()] if piece else "empty"
                tile=Image.open(ROOT/"work/coach-vision-fixture"/folder/(chess.square_name(square)+".png")).convert("RGB")
                picture.paste(tile.resize((98,98)),(chess.square_file(square)*98,(7-chess.square_rank(square))*98))
            board_window=tk.Toplevel(app.root);board_window.title("ChessLab Local Board")
            board_window.geometry("784x784+100+80")
            rendered=ImageTk.PhotoImage(picture,master=board_window)
            tk.Label(board_window,image=rendered,borderwidth=0,highlightthickness=0).pack()
            app.fen.set(AFTER_E4_E5)
            app.root.update_idletasks()
        heartbeats=[];errors=[];results={};phase=["activation"];started=time.monotonic()
        # Tambahkan latensi terukur untuk memastikan heartbeat Tk tidak tertahan HTTP.
        original_call=app.license_manager.api.call
        def slow_call(*args,**kwargs):
            time.sleep(.4)
            return original_call(*args,**kwargs)
        app.license_manager.api.call=slow_call
        app.license_controller.refresh(issued.json()["license_key"])
        future=[None]
        def heartbeat():
            if not app.closed:
                heartbeats.append(time.monotonic());app.root.after(20,heartbeat)
        def tick():
            try:
                if time.monotonic()-started>25:raise AssertionError("Lifecycle Tk melewati batas waktu")
                if phase[0]=="activation" and app.license_manager.entitled:
                    results["activation"]=True
                    assert len(heartbeats)>=8
                    if training:
                        board_window.lift();board_window.focus_force();app.root.update_idletasks()
                        hwnd=ctypes.windll.user32.GetParent(board_window.winfo_id()) or board_window.winfo_id()
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                    else:
                        app._auto_find=lambda token:None
                    app.start(automatic=True)
                    assert app.running
                    if training:
                        phase[0]="training"
                    else:
                        future[0]=app.service.submit(chess.Board(),.18)
                        phase[0]="engine"
                elif phase[0]=="training" and app.advice is not None and app.overlay.visible:
                    assert app.active_board.board_fen()==position.board_fen()
                    assert app.advice.move in app.active_board.legal_moves
                    results.update(stockfish=True,capture_vision_overlay=True)
                    response=client.post("/api/v1/admin/licenses/"+license_id+"/revoke",json={"reason":"Siklus QA papan latihan selesai"});response.raise_for_status()
                    app.license_controller.refresh();phase[0]="revoked"
                elif phase[0]=="engine" and future[0].done():
                    assert future[0].result().move in chess.Board().legal_moves
                    results["stockfish"]=True
                    response=client.post("/api/v1/admin/licenses/"+license_id+"/revoke",json={"reason":"Siklus QA desktop selesai"});response.raise_for_status()
                    app.license_controller.refresh()
                    phase[0]="revoked"
                elif phase[0]=="revoked" and app.license_controller.future is None and not app.license_manager.entitled:
                    assert not app.running and app.advice is None
                    results.update(revocation_stops_premium=True,heartbeat_count=len(heartbeats),ok=True)
                    app.close();return
            except Exception as exc:
                errors.append(str(exc)+" | "+app.status.get());app.close();return
            app.root.after(30,tick)
        app.root.after(0,heartbeat);app.root.after(30,tick)
        app.run()
        client.post("/api/v1/admin/auth/logout",json={})
        if errors:raise RuntimeError("; ".join(errors))
        assert results.get("ok"),"Uji berakhir sebelum lifecycle selesai"
        (work/"result.json").write_text(json.dumps(results,indent=2))
        (ROOT/"work"/"tk-license-result.json").write_text(json.dumps(results,indent=2))
        print(json.dumps(results,indent=2))


if __name__=="__main__":main()
