import csv
import io
import os

from flask import Blueprint, Response, redirect, render_template, request, url_for

from CTFd.models import Users, db
from CTFd.plugins import (
    override_template,
    register_admin_plugin_menu_bar,
    register_plugin_assets_directory,
)
from CTFd.plugins.migrations import upgrade
from CTFd.utils import get_config
from CTFd.utils.decorators import admins_only
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)
from CTFd.utils.modes import USERS_MODE, generate_account_url, get_mode_as_word
from CTFd.utils.scores import get_standings

PER_PAGE = 50


class StudentInfo(db.Model):
    __tablename__ = "enhanced_for_educate_students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    school = db.Column(db.String(128))
    student_class = db.Column(db.String(128))

    user = db.relationship("Users", foreign_keys=[user_id])


enhanced_for_educate = Blueprint(
    "enhanced_for_educate",
    __name__,
    template_folder="templates",
    static_folder="assets",
)


def _render_students_listing(import_result=None):
    q = request.args.get("q", "").strip()
    page = abs(request.args.get("page", 1, type=int))

    query = Users.query.outerjoin(StudentInfo, Users.id == StudentInfo.user_id)
    if q:
        like = "%{}%".format(q)
        query = query.filter(
            db.or_(
                Users.name.ilike(like),
                Users.email.ilike(like),
                StudentInfo.school.ilike(like),
                StudentInfo.student_class.ilike(like),
            )
        )

    pagination = query.order_by(Users.id.asc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )

    user_ids = [u.id for u in pagination.items]
    infos = {
        i.user_id: i for i in StudentInfo.query.filter(StudentInfo.user_id.in_(user_ids))
    }

    args = dict(request.args)
    args.pop("page", None)

    prev_page = (
        url_for("enhanced_for_educate.students_listing", page=pagination.prev_num, **args)
        if pagination.has_prev
        else None
    )
    next_page = (
        url_for("enhanced_for_educate.students_listing", page=pagination.next_num, **args)
        if pagination.has_next
        else None
    )

    return render_template(
        "plugins/enhanced_for_educate/templates/students.html",
        users=pagination.items,
        infos=infos,
        pagination=pagination,
        q=q,
        prev_page=prev_page,
        next_page=next_page,
        import_result=import_result,
    )


@enhanced_for_educate.route("/admin/enhanced_for_educate/students", methods=["GET"])
@admins_only
def students_listing():
    return _render_students_listing()


@enhanced_for_educate.route(
    "/admin/enhanced_for_educate/students/<int:user_id>", methods=["POST"]
)
@admins_only
def students_update(user_id):
    user = Users.query.get_or_404(user_id)
    info = StudentInfo.query.filter_by(user_id=user.id).first()
    if info is None:
        info = StudentInfo(user_id=user.id)
        db.session.add(info)

    info.school = request.form.get("school", "").strip() or None
    info.student_class = request.form.get("student_class", "").strip() or None
    db.session.commit()

    redirect_args = {}
    if request.form.get("q"):
        redirect_args["q"] = request.form.get("q")
    if request.form.get("page"):
        redirect_args["page"] = request.form.get("page")
    return redirect(url_for("enhanced_for_educate.students_listing", **redirect_args))


@enhanced_for_educate.route("/admin/enhanced_for_educate/students/import", methods=["POST"])
@admins_only
def students_import():
    result = {"created": 0, "updated": 0, "not_found": [], "errors": []}

    file = request.files.get("csv_file")
    if file is None or file.filename == "":
        result["errors"].append("No file was uploaded.")
        return _render_students_listing(import_result=result)

    try:
        content = file.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        result["errors"].append("Could not read the file. Please upload a UTF-8 CSV file.")
        return _render_students_listing(import_result=result)

    reader = csv.DictReader(io.StringIO(content, newline=None))
    columns = {(name or "").strip().lower(): name for name in (reader.fieldnames or [])}

    email_key = columns.get("email")
    school_key = columns.get("school")
    class_key = columns.get("class") or columns.get("student_class")

    if email_key is None:
        result["errors"].append('The CSV file must have an "email" column.')
        return _render_students_listing(import_result=result)

    for row in reader:
        email = (row.get(email_key) or "").strip()
        if not email:
            continue

        user = Users.query.filter(Users.email.ilike(email)).first()
        if user is None:
            result["not_found"].append(email)
            continue

        info = StudentInfo.query.filter_by(user_id=user.id).first()
        created = info is None
        if info is None:
            info = StudentInfo(user_id=user.id)
            db.session.add(info)

        if school_key is not None:
            info.school = (row.get(school_key) or "").strip() or None
        if class_key is not None:
            info.student_class = (row.get(class_key) or "").strip() or None

        result["created" if created else "updated"] += 1

    db.session.commit()

    return _render_students_listing(import_result=result)


@enhanced_for_educate.route("/admin/enhanced_for_educate/students/template", methods=["GET"])
@admins_only
def students_csv_template():
    content = "email,school,class\nstudent1@example.com,Example High School,101\n"
    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_template.csv"},
    )


@enhanced_for_educate.route("/admin/enhanced_for_educate/students/export", methods=["GET"])
@admins_only
def students_export():
    rows = (
        db.session.query(
            Users.email, Users.name, StudentInfo.school, StudentInfo.student_class
        )
        .outerjoin(StudentInfo, Users.id == StudentInfo.user_id)
        .order_by(Users.id.asc())
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "name", "school", "class"])
    for email, name, school, student_class in rows:
        writer.writerow([email or "", name or "", school or "", student_class or ""])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_export.csv"},
    )


@enhanced_for_educate.route("/plugins/enhanced_for_educate/scoreboard.json", methods=["GET"])
@check_account_visibility
@check_score_visibility
def scoreboard_data():
    standings = get_standings()
    mode = get_config("user_mode")
    account_type = get_mode_as_word()

    account_ids = [s.account_id for s in standings]
    infos = {}
    if mode == USERS_MODE and account_ids:
        infos = {
            i.user_id: i
            for i in StudentInfo.query.filter(StudentInfo.user_id.in_(account_ids))
        }

    data = []
    for i, s in enumerate(standings):
        info = infos.get(s.account_id)
        data.append(
            {
                "pos": i + 1,
                "account_id": s.account_id,
                "account_url": generate_account_url(account_id=s.account_id),
                "account_type": account_type,
                "name": s.name,
                "score": int(s.score),
                "bracket_id": s.bracket_id,
                "bracket_name": s.bracket_name,
                "school": info.school if info else None,
                "student_class": info.student_class if info else None,
            }
        )
    return {"success": True, "data": data}


def load(app):
    upgrade(plugin_name="enhanced_for_educate")

    app.register_blueprint(enhanced_for_educate)

    register_plugin_assets_directory(
        app, base_path="/plugins/enhanced_for_educate/assets/"
    )
    register_admin_plugin_menu_bar(
        title="Students", route="/admin/enhanced_for_educate/students"
    )

    template_path = os.path.join(
        os.path.dirname(__file__), "templates", "scoreboard_override.html"
    )
    with open(template_path, encoding="utf-8") as f:
        override_template("scoreboard.html", f.read())
