You'll need to get Vaurien from the master branch off of github:

Repo: https://github.com/mozilla-services/vaurien

Mocking out MySQL:

    make chaos_mysql

Mocking out redis:

    make chaos_redis

Notes:
    
* Adding just a 0.01 second delay to mysql causes the test runs to
  go from 6 seconds to 106 seconds on my laptop.
* 
