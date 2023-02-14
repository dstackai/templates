declare type THubBackendType = 'aws';
declare interface IHub {
    hub_name: string,
    backend: { type: THubBackendType } & THubBackendAWS,
    members: IHubMember[]
}


declare interface THubBackendAWS {
    access_key: string,
    secret_key: string,
    region_name: string,
    s3_bucket_name: string,
    ec2_subnet_id: string,
}

declare interface IHubMember {
    user_name: string,
    hub_role: THubRole,
}

declare type THubRole = 'read' | 'run' | 'admin'
