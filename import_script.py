# Copyright (c) 2021 Yoann Piétri
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

"""
This script imports users from a CSV file.

Each row must be formatted as such :
Last name - First name - email - room

The room must be in format BuildingRoom, for instance A101-2
The username will be generated from the local part of email.
Parameters :

- PATH : The path of the CSV file (either relative or absolute)
- SCHOOL_ID : the school that will be used for all the users
- ARTICLES : list of (id, quantity) to automatically add to every user. Set to [] to add no article.
- PAYMENT_METHOD : the payment method for the articles
- COMMENT : comment to add to every user
"""

# Imports

import csv

from cotisations.models import Article, Facture, Paiement, Vente
from django.db import transaction
from django.test import Client
from topologie.models import Building, Room
from users.models import Adherent, School, User

# Paramaters

PATH = "./list-users.csv"
SCHOOL_ID = 1  # The school id in which to add the user
ARTICLES = [
    (1, 4)
]  # The article to set to the user in the format (id, quantity). Let empty to add no article.
PAYMENT_METHOD = 1  # Payment method for the articles.
COMMENT = "Example"  # Comment that will be added to every user created

# Code


class CSVUser:
    """
    Class representing a user imported from the CSV.
    """

    def __init__(self, last_name, first_name, email, room):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.username = self.get_username()
        self.room = self.get_room(room)

    def __str__(self):
        """String representation

        Returns:
            string: string representation
        """
        return "{} ({} {}) - {} ({})".format(
            self.username, self.first_name, self.last_name, self.email, self.room
        )

    def get_username(self):
        """Get username from email.

        Return local part of email replacing dots with dashes

        Args:
            email (string): email of the user

        Returns:
            string: username of the user
        """
        local_part = self.email.split("@")[0]
        return local_part.replace(".", "-")

    def get_room(self, room):
        """Get room object from room name

        Args:
            room (string): room name

        Returns:
            Room: room object
        """
        index = room.index(" ")
        building_name = room[:index]
        name = room[index + 1 :]
        building = Building.objects.get(name=building_name)
        return Room.objects.get(building=building, name=name)


def read_file():
    """Read CSV file

    Returns:
        list(CSVUser): list of the users in the CSVUser format.
    """
    users = []
    with open(PATH, "rt") as f:
        data = csv.reader(f)
        for row in data:
            user = CSVUser(row[0], row[1], row[2], row[3])
            users.append(user)
    return users


def check_constraints(usernames):
    """Check if one the usernames is already taken.

    Args:
        usernames (list of string): list of usernames

    Raises:
        Exception: ifone or more of the usernames is/are already taken.
    """
    query = Adherent.objects.filter(pseudo__in=usernames)
    if query:
        raise Exception(
            "The following usernames are not unique : {}".format(
                ", ".join([a.pseudo for a in query])
            )
        )


def force_move(room):
    """Force the move from a room

    Args:
        room (Room): the room object
    """
    already_in_room = Adherent.objects.filter(room=room)
    if already_in_room:
        previous_user = already_in_room[0]
        previous_user.room = None
        previous_user.save()


@transaction.atomic
def transaction():
    """
    Actually make the operation on database. No operation will be written if an error occurs (atomic transaction).
    """
    school = School.objects.get(pk=SCHOOL_ID)
    payment = Paiement.objects.get(pk=PAYMENT_METHOD)
    users = read_file()
    print("{} users detected".format(len(users)))
    print("Verifying that no conflict occurs for usernames")
    check_constraints([user.username for user in users])
    print("Usernames OK")
    print("Creating accounts")
    for user in users:
        force_move(user.room)
        Adherent.objects.create(
            surname=user.last_name,
            pseudo=user.username,
            email=user.email,
            school=school,
            comment=COMMENT,
            state=User.STATE_ACTIVE,
            email_state=User.EMAIL_STATE_VERIFIED,
            name=user.first_name,
            room=user.room,
        )
    print("Accountts created")
    print("Reseting password")
    for user in users:
        c = Client()
        c.post("/users/reset_password/", {"pseudo": user.username, "email": user.email})
    print("Passwords reset")
    if ARTICLES:
        print("Adding subscriptions")
        for user in users:
            user_object = User.objects.get(pseudo=user.username)

            invoice = Facture.objects.create(user=user_object, paiement=payment)

            purchases = []
            total_price = 0
            for art in ARTICLES:
                article = Article.objects.get(pk=art[0])
                quantity = art[1]
                total_price += article.prix * quantity
                new_purchase = Vente(
                    facture=invoice,
                    name=article.name,
                    prix=article.prix,
                    duration_connection=article.duration_connection,
                    duration_days_connection=article.duration_days_connection,
                    duration_membership=article.duration_membership,
                    duration_days_membership=article.duration_days_membership,
                    number=quantity,
                )
                purchases.append(new_purchase)
            invoice.save()
            for p in purchases:
                p.facture = invoice
                p.save()
            invoice.valid = True
            invoice.control = True
            invoice.save()
        print("Subscriptions created")
    print("All went well")


transaction()
