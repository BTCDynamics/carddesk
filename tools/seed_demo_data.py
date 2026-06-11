import argparse
import os
import random
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)



from app import app, db
from models import Card, IntakeBatch, DealerEvent, CardImportStaging, CompRefreshQueue


SHOW_LOCATIONS = ["Showcase A", "Showcase B", "Showcase C", "Value Box", "Vintage Box", "Football Box", "Basketball Box"]
BACKSTOCK_LOCATIONS = ["Backstock A", "Backstock B", "Processing Box"]

BATCHES = [
    ("Vintage Collection Purchase", "Vintage Box", "Collection Purchase", "Estate Buy Demo"),
    ("National Show Pickup", "Showcase A", "Card Show Purchase", "National Demo Pickup"),
    ("Dollar Box Batch A", "Value Box", "Bulk Lot", "Dollar Box Demo Lot"),
    ("Modern Stars Intake", "Showcase B", "Existing Inventory", "Modern Inventory Demo"),
    ("PSA Slab Intake Demo", "Showcase C", "PSA Submission Return", "Graded Slab Demo"),
]

CARD_POOL = [
    ("Mickey Mantle","Baseball",1958,"Topps","Base","150",True,False,650),
    ("Willie Mays","Baseball",1965,"Topps","Base","250",True,False,180),
    ("Hank Aaron","Baseball",1969,"Topps","Base","100",True,False,140),
    ("Roberto Clemente","Baseball",1972,"Topps","Base","309",True,False,225),
    ("Nolan Ryan","Baseball",1971,"Topps","Base","513",True,False,160),
    ("Johnny Bench","Baseball",1968,"Topps","Rookie Stars","247",True,True,420),
    ("George Brett","Baseball",1975,"Topps","Rookie","228",True,True,170),
    ("Rickey Henderson","Baseball",1980,"Topps","Rookie","482",True,True,230),
    ("Steve Carlton","Baseball",1981,"Topps","Base","630",True,False,28),
    ("Mike Schmidt","Baseball",1974,"Topps","Base","283",True,False,85),
    ("Carlton Fisk","Baseball",1972,"Topps","Rookie Stars","79",True,True,130),
    ("Pete Rose","Baseball",1976,"Topps","Base","240",False,False,65),
    ("Reggie Jackson","Baseball",1970,"Topps","Base","140",True,False,95),
    ("Ozzie Smith","Baseball",1979,"Topps","Rookie","116",True,True,180),
    ("Cal Ripken Jr.","Baseball",1982,"Topps Traded","Rookie","98T",True,True,210),
    ("Ken Griffey Jr.","Baseball",1989,"Upper Deck","Rookie","1",True,True,120),
    ("Frank Thomas","Baseball",1990,"Leaf","Rookie","300",True,True,75),
    ("Derek Jeter","Baseball",1993,"SP","Rookie","279",True,True,450),
    ("Albert Pujols","Baseball",2001,"Topps","Rookie","596",True,True,90),
    ("Ichiro Suzuki","Baseball",2001,"Topps","Rookie","726",True,True,85),
    ("Mike Trout","Baseball",2011,"Topps Update","Rookie","US175",False,True,350),
    ("Shohei Ohtani","Baseball",2018,"Topps Update","Rookie","US1",False,True,120),
    ("Ronald Acuna Jr.","Baseball",2018,"Topps Update","Rookie","US250",False,True,85),
    ("Juan Soto","Baseball",2018,"Topps Update","Rookie","US300",False,True,90),
    ("Aaron Judge","Baseball",2017,"Topps","Rookie","287",False,True,95),
    ("Tom Brady","Football",2000,"Bowman","Rookie","236",False,True,600),
    ("Patrick Mahomes","Football",2017,"Donruss Optic","Rated Rookie","177",False,True,260),
    ("Josh Allen","Football",2018,"Prizm","Rookie","205",False,True,180),
    ("Joe Burrow","Football",2020,"Prizm","Rookie","307",False,True,150),
    ("Justin Jefferson","Football",2020,"Prizm","Rookie","398",False,True,80),
    ("Caleb Williams","Football",2024,"Prizm Draft","Rookie","101",False,True,65),
    ("Jayden Daniels","Football",2024,"Prizm Draft","Rookie","102",False,True,60),
    ("Peyton Manning","Football",1998,"Topps Chrome","Rookie","165",True,True,220),
    ("Jerry Rice","Football",1986,"Topps","Rookie","161",True,True,350),
    ("Walter Payton","Football",1976,"Topps","Base","148",True,False,210),
    ("Michael Jordan","Basketball",1989,"Hoops","Base","200",True,False,45),
    ("Kobe Bryant","Basketball",1996,"Topps","Rookie","138",True,True,260),
    ("LeBron James","Basketball",2003,"Topps","Rookie","221",False,True,420),
    ("Stephen Curry","Basketball",2009,"Panini","Rookie","307",False,True,240),
    ("Kevin Durant","Basketball",2007,"Topps","Rookie","112",False,True,130),
    ("Victor Wembanyama","Basketball",2023,"Prizm","Rookie","136",False,True,140),
    ("Anthony Edwards","Basketball",2020,"Prizm","Rookie","258",False,True,85),
    ("Luka Doncic","Basketball",2018,"Prizm","Rookie","280",False,True,210),
    ("Shaquille O'Neal","Basketball",1992,"Topps","Rookie","362",True,True,55),
    ("Tim Duncan","Basketball",1997,"Topps Chrome","Rookie","115",True,True,95),
    ("Wayne Gretzky","Hockey",1980,"Topps","Base","250",True,False,180),
    ("Mario Lemieux","Hockey",1985,"O-Pee-Chee","Rookie","9",True,True,300),
    ("Sidney Crosby","Hockey",2005,"Upper Deck","Young Guns","201",False,True,320),
    ("Connor McDavid","Hockey",2015,"Upper Deck","Young Guns","201",False,True,400),
    ("Alex Ovechkin","Hockey",2005,"Upper Deck","Rookie","443",False,True,150),
]

VARIATIONS = ["Base", "Refractor", "Silver", "Chrome", "Update", "Insert", "Parallel", "Holo", "Gold"]
GRADES = ["7", "8", "8.5", "9", "10"]
GRADERS = ["PSA", "SGC", "BGS"]


def font(size):
    for p in [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def center(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    words = str(text).split()
    lines, cur = [], ""
    maxw = x2 - x1
    for w in words:
        test = (cur + " " + w).strip()
        bb = draw.textbbox((0,0), test, font=fnt)
        if bb[2] - bb[0] <= maxw or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = int(getattr(fnt, "size", 20) * 1.15)
    total = lh * len(lines)
    y = y1 + ((y2-y1)-total)/2
    for line in lines:
        bb = draw.textbbox((0,0), line, font=fnt)
        draw.text((x1 + (maxw-(bb[2]-bb[0]))/2, y), line, font=fnt, fill=fill)
        y += lh


def make_image(path, card_type, player, year, brand, sport, grade_text):
    w, h = (720, 1000) if card_type == "Raw" else (760, 1080)
    top = {"Baseball":(22,163,74), "Football":(245,158,11), "Basketball":(239,68,68), "Hockey":(14,165,233)}.get(sport, (14,165,233))
    bottom = (15,23,42)
    img = Image.new("RGB", (w,h), top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        r = y/(h-1)
        c = tuple(int(top[i]*(1-r)+bottom[i]*r) for i in range(3))
        d.line([(0,y),(w,y)], fill=c)

    f_big, f_mid, f_small, f_tiny = font(52), font(30), font(22), font(16)

    if card_type == "Graded":
        d.rounded_rectangle([28,24,w-28,h-24], radius=34, fill=(235,241,248), outline=(15,23,42), width=6)
        d.rounded_rectangle([58,55,w-58,180], radius=14, fill=(248,250,252), outline=(15,23,42), width=3)
        d.text((78,76), grade_text, font=f_mid, fill=(15,23,42))
        d.text((78,124), f"{year} {brand}", font=f_small, fill=(51,65,85))
        x1,y1,x2,y2 = 88,230,w-88,h-85
    else:
        d.rounded_rectangle([40,45,w-40,h-45], radius=28, fill=(248,250,252), outline=(15,23,42), width=6)
        x1,y1,x2,y2 = 70,85,w-70,h-75

    d.rounded_rectangle([x1,y1,x2,y2], radius=22, fill=(15,23,42), outline=(255,255,255), width=4)
    cx = (x1+x2)//2
    d.ellipse([cx-70,y1+140,cx+70,y1+280], fill=(226,232,240))
    d.rounded_rectangle([cx-100,y1+280,cx+100,y1+525], radius=42, fill=(226,232,240))
    d.rectangle([x1+36,y2-230,x2-36,y2-45], fill=(241,245,249))
    center(d, (x1+45,y2-218,x2-45,y2-145), player.upper(), f_big, (15,23,42))
    center(d, (x1+45,y2-136,x2-45,y2-84), f"{year} {brand}", f_mid, (51,65,85))
    center(d, (x1+45,y2-72,x2-45,y2-36), sport, f_small, (22,101,52))
    d.text((58 if card_type=="Raw" else 80, h-36), "DEMO IMAGE • NOT A REAL CARD SCAN", font=f_tiny, fill=(100,116,139))
    img.save(path, quality=90)


def wipe(upload_folder):
    Card.query.delete()
    CardImportStaging.query.delete()
    CompRefreshQueue.query.delete()
    DealerEvent.query.delete()
    IntakeBatch.query.delete()
    db.session.commit()
    if os.path.isdir(upload_folder):
        for fn in os.listdir(upload_folder):
            if fn.lower().startswith("demo_card_"):
                try:
                    os.remove(os.path.join(upload_folder, fn))
                except OSError:
                    pass


def main(do_wipe=False):
    random.seed(95)
    with app.app_context():
        db.create_all()
        upload_folder = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)

        if Card.query.count() and not do_wipe:
            print("Cards already exist. Run with --wipe to reset demo/test records first.")
            return
        if do_wipe:
            print("Wiping existing demo/test records...")
            wipe(upload_folder)

        batches = {}
        for name, location, source, event in BATCHES:
            b = IntakeBatch(
                batch_name=name,
                status="Closed",
                notes=f"Demo batch: {name}",
                default_sport="Baseball",
                default_card_type="Raw",
                default_collection_type="Inventory",
                default_status="Active",
                default_storage_location=location,
                default_acquisition_source=source,
                default_acquisition_event=event,
                default_acquisition_date=str(date.today() - timedelta(days=random.randint(20,240))),
            )
            db.session.add(b)
            batches[name] = b
        db.session.flush()

        created = 0
        for i in range(320):
            player,sport,year,brand,set_name,num,hof,rookie,base_value = random.choice(CARD_POOL)
            is_graded = random.random() < 0.36
            card_type = "Graded" if is_graded else "Raw"
            grader = random.choice(GRADERS) if is_graded else None
            grade = random.choice(GRADES) if is_graded else None
            grade_text = f"{grader} {grade}" if is_graded else ""

            multiplier = random.uniform(0.65, 1.35) * (random.uniform(1.35,2.8) if is_graded else 1)
            estimated = round(max(3, base_value * multiplier), 2)
            asking = round(estimated * random.uniform(.92,1.22), 2)
            cost = round(estimated * random.uniform(.35,.72), 2)

            if sport == "Football":
                storage = random.choice(["Football Box","Showcase C","Backstock A"]); batch = batches[random.choice(["National Show Pickup","Modern Stars Intake"])]
            elif sport == "Basketball":
                storage = random.choice(["Basketball Box","Showcase B","Showcase C"]); batch = batches[random.choice(["National Show Pickup","Modern Stars Intake"])]
            elif is_graded:
                storage = random.choice(["Showcase A","Showcase B","Showcase C"]); batch = batches[random.choice(["PSA Slab Intake Demo","National Show Pickup"])]
            elif year <= 1985:
                storage = random.choice(["Vintage Box","Showcase A"]); batch = batches["Vintage Collection Purchase"]
            elif asking <= 25:
                storage = "Value Box"; batch = batches["Dollar Box Batch A"]
            else:
                storage = random.choice(SHOW_LOCATIONS + BACKSTOCK_LOCATIONS); batch = batches[random.choice(list(batches.keys()))]

            img_name = f"demo_card_{i+1:04d}.jpg"
            make_image(os.path.join(upload_folder, img_name), card_type, player, year, brand, sport, grade_text)
            acquired = date.today() - timedelta(days=random.randint(5,420))

            db.session.add(Card(
                card_code=f"DEMO-{i+1:04d}",
                player_name=player,
                year=year,
                sport=sport,
                brand=brand,
                set_name=set_name,
                card_number=str(num),
                variation=random.choice(VARIATIONS),
                is_hof=hof,
                is_rookie=rookie,
                card_type=card_type,
                grading_company=grader,
                actual_grade=grade,
                cert_number=str(random.randint(10000000,99999999)) if is_graded else "",
                grade_estimate="" if is_graded else random.choice(["EX","VG-EX","NM","NM-MT",""]),
                quantity=1,
                purchase_price=cost,
                estimated_value=estimated,
                asking_price=asking,
                purchase_date=str(acquired),
                acquisition_source=batch.default_acquisition_source,
                acquisition_date=str(acquired),
                acquisition_event=batch.default_acquisition_event,
                intake_batch_id=batch.id,
                storage_location=storage,
                image_filename=img_name,
                notes="Demo inventory record generated for CardDesk testing.",
                status="Active",
                collection_type="Inventory",
                fulfillment_status="In Storage",
            ))
            created += 1

        db.session.add(DealerEvent(
            event_name="2026 Tupelo Card Show Demo",
            location="Tupelo, MS",
            start_date=str(date.today() + timedelta(days=14)),
            end_date=str(date.today() + timedelta(days=15)),
            status="Planned",
            notes="Demo event for Show Prep and Customer Search testing.",
            table_fee=125,
            travel_expense=45,
            food_expense=30,
            selected_show_locations="\n".join(SHOW_LOCATIONS),
        ))

        db.session.commit()
        print(f"Demo inventory loaded: {created} cards")
        print(f"Images created in: {upload_folder}")
        print("Try Customer Search: Carlton, PSA, Rookie, Jordan, Brady, Ohtani, Topps")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true")
    args = parser.parse_args()
    main(do_wipe=args.wipe)
