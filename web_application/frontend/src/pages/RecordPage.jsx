import React from 'react';
import FaceRecorder from '../components/features/FaceRecorder';
import { Container, Row, Col } from 'react-bootstrap';

const RecordPage = () => {
  return (
    <Container className="mt-4">
      <Row className="justify-content-center">
        <Col md={10} lg={8}>
          <h2 className="text-center mb-4">In-Cabin Recording</h2>
          <p className="text-muted text-center">
            Position your phone to face you clearly. The system will detect your head pose for mirror check calibration.
          </p>
          <FaceRecorder />
        </Col>
      </Row>
    </Container>
  );
};

export default RecordPage;
