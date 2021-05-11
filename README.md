# Re2o Import Script

This is a script to import users from a CSV file for [re2o](https://gitlab.federez.net/re2o/re2o).

The CSV mut be formatted as such :

`Last name - First name - email - room`

The room must be in format BuildingRoom, for instance A101-2
The username will be generated from the local part of email.

An example CSV is given in the repository.