export interface SubscriptionConfirmation {
    Type: string;
    MessageId: string;
    Token: string;
    TopicArn: string;
    Message: string;
    SubscribeURL: string;
    Timestamp: string;
    SignatureVersion: string;
    Signature: string;
    SigningCertURL: string;
}