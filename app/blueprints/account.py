"""Sign in, create an account, sign out."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for

from .. import auth

bp = Blueprint("account", __name__)


@bp.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if auth.current_user() and request.method == "GET":
        return redirect(url_for("public.home"))
    error, email = None, ""
    if request.method == "POST":
        email = request.form.get("email", "")
        try:
            auth.authenticate(email, request.form.get("password", ""))
            return redirect(auth.safe_next(request.form.get("next")))
        except auth.SignInError as exc:
            error = str(exc)
    return render_template("account/sign_in.html", error=error, email=email,
                           next=request.values.get("next", "")), (400 if error else 200)


@bp.route("/create-account", methods=["GET", "POST"])
def create_account():
    if auth.current_user() and request.method == "GET":
        return redirect(url_for("public.home"))
    errors: dict[str, str] = {}
    form = {"first_name": "", "last_name": "", "email": "", "intent": request.args.get("as", "student")}
    if request.method == "POST":
        form = {k: request.form.get(k, "") for k in ("first_name", "last_name", "email", "intent")}
        try:
            auth.create_account(password=request.form.get("password", ""), **form)
            return redirect(url_for("public.home", welcome=1))
        except auth.SignUpError as exc:
            errors[exc.field] = exc.message
    return render_template("account/create_account.html", form=form, errors=errors), (400 if errors else 200)


@bp.post("/sign-out")
def sign_out():
    auth.sign_out()
    return redirect(url_for("public.home"))
