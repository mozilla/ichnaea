Instructions to setup your own loadtesting infrastructure for ichnaea:

The short version:

1. Get a new devstack running.
2. Spin up an EC2 instance to initiate load tests.
3. Install your MySQL fixture data
    ```
    MYSQL_HOST="your_rds_endpoint_here" make install_fixtures
    ```

4. Run the two submission tests:

    ```
    make submit_cell
    make submit_wifi
    ```

Run the query tests:

    ```
    make query_cell
    make query_wifi
    make query_cell_mixed
    ```

---

The longer version if you have to use CloudFormation:

You'll first need to clone the mozilla-services/svcops repository
from:

https://github.com/mozilla-services/svcops

You can find instructions to setup a dev stack for Ichnaea here:

https://github.com/mozilla-services/svcops/blob/master/cloudformations/location/docs/making-a-dev-stack

When you create the my-location-stack.yaml file, you will need to edit
the `vars` section.

The `stack_name` should be set to a unique name.

Note that the North Carolina is us-west-1.and Oregon region is
us-west-2.

`owner` should be updated to your own user id.

`ami_id` The AMI you will want to select is the latest stable AMI with the
'SvcOps' label attached to it.  Note that AMIs are region specific.

`keyname` should be set to your user id.

`snsdest` should be set to your mozilla email address.

Example configuration:

```
  vars:
    stack_name: locvng-west2
    region: us-west-2
    owner: vng
    ami_id: ami-6afe9e5a
    keyname: vng
    snsdest: vng@mozilla.com
```

Once your stack is running, you'll need to generate and then bulkload
a dataset into the mysql master.

Launch an EC2 instance that will act as your client to do load testing
with.  You'll need to get the private IP address as you will be using
it when provisioning a new security group for your RDS instance.

Provision a new database security group with write privileges and get
the mysql connection setup from Amazon RDS.

Set the connection type to be CIDR/IP and add the private IP from your
newly created EC2 instance.

You should have something like:

```
10.254.27.93/32
```

Now you'll need to assign the security group to your RDS instance.
Select your RDS instance in the RDS Dashboard and scroll down and
select the "Instance Actions" to modify the instance and add the new
security group.

Go back to the RDS dashboard and find your instance and grab the
endpoint name, you'll need that to configure the load test clients.

Your MySQL hostname needs to be added to the loadtest_env.sh script 
the settings 

Find your ELB instance and add that to your loadtest_env.sh script

You should now be able to run the load tests from your single loads
node using make.
