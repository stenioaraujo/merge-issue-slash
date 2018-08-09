# GitLab Merges and Issues Slack slash command
This a webserver to provide functionalities for a slash command integration with Slack.

## Requirements
- Gitlab Personal Token
  - This version of the app uses a user gitlab token to access information about Merges and Issues, **the slash command will only show information about groups to which the Personal Token  has enough access to.** 
- Slack Signing Secret
  - This Key is provided to each app you create, **this should be the one related to the app that will have the slash command**
- Python and Pip or Docker and Docker-Compose
- Public Floating IP
- Open Port `8080`

## Server Deployment
You will need external access to the server, so your server needs a Plublic IP address.

The app is setup only to work with HTTPS, this way is safer and your tokens won't be shared with eavesdroppers. However, **if you use HTTPS, slack only works if the server's certificate is signed by a known CA**. A good, cheap and easy way of aquiring your own Valid Certificate is using [Let's Encrypt](https://letsencrypt.org/). And a good way of getting a free domain for you is using [DuckDns](https://www.duckdns.org/).

You have two alternatives to deploy the app:
- Use Docker
- Deploy on the host
Bellow is described only instruction on how to deploy using Docker.

### Use Docker
Docker makes it easier to deploy the application. Bellow are the instruction to install docker in the root namespace (This mean you will need to use sudo to run the docker commands from another user, this implies security issues, you may find more information [here](https://docs.docker.com/install/linux/linux-postinstall/#manage-docker-as-a-non-root-user)).

- Install Docker

```bash
sudo apt-get update
sudo apt-get -y install \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
sudo apt-get update
sudo apt-get -y install docker-ce
sudo usermod -aG docker $USER
# close session and login again to refresh groups
docker run hello-world
```

- Install Docker-Compose

```bash
sudo curl -L https://github.com/docker/compose/releases/download/1.20.1/docker-compose-`uname -s`-`uname -m` -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

The repository comes with a `docker-compose.yaml` ready to work. The only things you need to provide it are the following environment variables:
- ALLOWED_CHANNELS_IDS
  - Those are the Slack Channel which will have access to the slash command. If one runs the slash command in a unathourized channel, a courtesy message will be sent to that user. (e.g `ALLOWED_CHANNELS_IDS=D6THNR0CV,GBQAX1A9Y`)
- GITLAB_PERSONAL_TOKEN
  - This will give the application access to the GitLab API. **Only resources that a user has access will be available for the application**.
  - You may get your access token at [https://git.myserver.com/profile/personal_access_tokens](https://git.myserver.com/profile/personal_access_tokens)
- SECRET_ACCESS_KEY
  - This is just a secret that will be added to the URL to make sure the user that is sending the request know it. **This** **is not enough to have access to the GitLab's information.** **Only a valid request sent by Slack will be processed by the app**. (e.g. `SECRET_ACCESS_KEY=my-SuperSecret-Key`)
- SLACK_SIGNING_SECRET
  - This is a signing key that each App registered on Slack has, you may find more information about it at [Slack's official documentation](https://api.slack.com/docs/verifying-requests-from-slack).
  - If you don't have an Slack App you can use, you can create a new one, for that, just loging to the Slack workspace you will use and access the following page https://api.slack.com/apps. Instruction can be found [here](https://api.slack.com/slash-commands#getting_started).
- HTTPS_CERT
  - The full path of the HTTPS Certificate generated using Let's Encrypt.
- HTTPS_KEY
  - The full path of the HTTPS Key generated using Let's Encrypt.
The HTTPS Certificate and Key need to be mounted on the Container where the application is running, make sure to provide the correct paths on the `docker-compose.yaml` file. The syntax Docker-Compose uses for its volumes may be seen [here](https://docs.docker.com/compose/compose-file/#short-syntax-3).
- Start the container

```bash
sudo docker-compose up -d
```

## Slack Configuration
At Slack, when you create your Application, you will need to create a Slash command to use this app. One of the required information to create the Slash command is the **Request URL**.

The **Request URL** is the URL to which Slack will send POST Requests when the slash command is used.

The URL the app is listening for is formated the following way: `https://**<SERVER_DOMAIN_WITH_VALID_CERTIFICATE>**:8080/slash?groups_names=**<LIST_OF_GROUPS_NAMES>**&token=**<SECRET_ACCESS_KEY>`**
- SERVER_DOMAIN_WITH_VALID_CERTIFICATE
  - Is the domain where your application is hosted. This domain was validated using Let's Encrypt.
- LIST_OF_GROUPS_NAMES
  - The list of groups names from where the application will get the Merge Requests and Issues. (e.g: `groups_names=general,hack-project`)
- SECRET_ACCESS_KEY
  - The same key defined in the `docker-compose.yaml` file in the last section.

## Using the application
Once you have the app running, and an application configured with a Slash command (named `/project` for example), you can ask for help on how to use it with the command: `/project help`
